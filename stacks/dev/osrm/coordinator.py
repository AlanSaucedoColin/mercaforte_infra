#!/usr/bin/env python3
"""Publica un conjunto efectivo de cierres junto al grafo que lo aplica, sin colas ni borradores"""

import fcntl
import hashlib
import hmac
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import logging
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import threading
import time
import urllib.request
import uuid

import osmium
import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from elevation import ElevationSampler
from elevation_tiles import ElevationTiles

DATA = Path(os.environ.get("ROUTING_DATA_ROOT", "/data")).resolve()
PBF = Path(os.environ.get("ROUTING_PBF", "/data/morelos.osm.pbf")).resolve()
VERSIONS = DATA / "routing-versions"
ACTIVE = DATA / "routing-active"
JOURNAL = DATA / "routing-switch.json"
BOOTSTRAP = DATA / "routing-bootstrap.json"
CATALOG = DATA / "routing-catalog.json"
PREPARE_TIMEOUT = int(os.environ.get("ROUTING_PREPARE_TIMEOUT", "900"))
HEALTH_URL = "http://127.0.0.1:5002/nearest/v1/driving/-99.2216,18.9242"
STOP = threading.Event()
LOG = logging.getLogger("routing")
WAY_ID = re.compile(r"[1-9][0-9]{0,19}\Z")
MAX_VERSION = 9007199254740991
HOP_HEADERS = {"connection", "keep-alive", "proxy-authenticate", "proxy-authorization", "te", "trailer",
               "transfer-encoding", "upgrade", "content-length"}


class ApiError(Exception):
    def __init__(self, status, code, detail):
        super().__init__(detail)
        self.status, self.code, self.detail = status, code, detail


def connect():
    return psycopg.connect(
        host=os.environ.get("ROUTING_DB_HOST", "postgres"),
        port=int(os.environ.get("ROUTING_DB_PORT", "5432")),
        dbname=os.environ.get("ROUTING_DB_NAME", "mercaforte"),
        user=os.environ.get("ROUTING_DB_USER", "mercaforte_app"),
        password=os.environ["ROUTING_DB_PASSWORD"],
        connect_timeout=5,
        options="-c statement_timeout=15000 -c lock_timeout=10000",
        row_factory=dict_row,
    )


def atomic_json(path, value):
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w") as output:
        json.dump(value, output)
        output.flush()
        os.fsync(output.fileno())
    os.replace(temporary, path)
    sync_directory(path.parent)


def sync_directory(path):
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def contained(path):
    resolved = Path(path).resolve()
    if not resolved.is_relative_to(DATA):
        raise ValueError("Routing path escapes the configured data directory")
    return resolved


def read_manifest(base):
    return json.loads(contained(Path(base).parent / "manifest.json").read_text())


def graph_exists(base):
    return all(Path(str(base) + suffix).is_file() for suffix in (
        ".properties", ".partition", ".cells", ".cell_metrics", ".ramIndex", ".fileIndex"
    ))


def active_base():
    if ACTIVE.is_symlink():
        return contained(ACTIVE) / "graph.osrm"
    return None


def set_active(base):
    base = contained(base)
    temporary = DATA / "routing-active.tmp"
    temporary.unlink(missing_ok=True)
    temporary.symlink_to(base.parent.relative_to(DATA), target_is_directory=True)
    os.replace(temporary, ACTIVE)
    sync_directory(DATA)


def dataset_hash():
    digest = hashlib.sha256()
    with PBF.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    for path in [Path("/opt/car.lua"), *sorted(Path("/opt/lib").rglob("*.lua"))]:
        digest.update(str(path.relative_to("/opt")).encode())
        digest.update(path.read_bytes())
    digest.update(b"OSRM-v6.0.0-routing-profile-v1")
    return digest.hexdigest()


def healthy():
    try:
        with urllib.request.urlopen(HEALTH_URL, timeout=2) as response:
            return json.load(response).get("code") == "Ok"
    except (OSError, ValueError):
        return False


class CatalogImporter(osmium.SimpleHandler):
    """Importa solamente vias admitidas por el mismo perfil usado para crear el grafo base"""

    def __init__(self, copy, eligible_ids):
        super().__init__()
        self.copy = copy
        self.eligible_ids = eligible_ids
        self.imported = set()

    def way(self, way):
        if str(way.id) not in self.eligible_ids:
            return
        coordinates = [[node.location.lon, node.location.lat] for node in way.nodes]
        if len(coordinates) < 2:
            raise ValueError("A routable OSM way has an incomplete geometry")
        longitude, latitude = zip(*coordinates)
        bounds = f"({max(longitude)},{max(latitude)}),({min(longitude)},{min(latitude)})"
        row = (str(way.id), way.tags.get("name"),
               Jsonb({"type": "LineString", "coordinates": coordinates}), bounds)
        self.copy.write_row(row)
        self.imported.add(str(way.id))


class Coordinator:
    """Supervisa el grafo publicado y serializa guardados directos con publicacion atomica"""

    def __init__(self):
        self.routed = None
        self.served_base = None
        self.fingerprint = None
        self.source_stamp = None
        self.manifest = None
        self.initialized = False
        self.catalog_ready = False
        self.map_changed = False
        self.available = False
        self.saving = False
        self.switching = True
        self.proxy_requests = 0
        self.condition = threading.Condition(threading.RLock())
        self.save_lock = threading.Lock()
        self.elevation_tiles = ElevationTiles(
            os.environ.get("ROUTING_ELEVATION_ROOT", str(DATA / "elevation"))
        )
        self.token = os.environ.get("ROUTING_MANAGER_TOKEN", "")
        if len(self.token) < 24:
            raise ValueError("ROUTING_MANAGER_TOKEN must contain at least 24 characters")

    def run_command(self, arguments, deadline, log_file):
        environment = dict(os.environ, LUA_PATH="/opt/?.lua;/opt/?/init.lua;;")
        with log_file.open("ab") as output:
            process = subprocess.Popen(arguments, cwd="/opt", env=environment,
                                       stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
            try:
                while process.poll() is None:
                    if STOP.wait(0.25):
                        raise InterruptedError("Coordinator is stopping")
                    if time.monotonic() >= deadline:
                        raise TimeoutError("Routing preparation exceeded its deadline")
                if process.returncode:
                    raise RuntimeError("OSRM preprocessing failed; inspect the version preparation log")
            finally:
                if process.poll() is None:
                    self.stop_process(process)

    def prepare_graph(self, version_name, blocked_ids, revision, catalog=False):
        directory = contained(VERSIONS / version_name)
        if directory.exists():
            raise RuntimeError("A routing version directory already exists")
        directory.mkdir()
        atomic_json(directory / ".routing-owned.json", {"format": "routing-version-v1", "name": directory.name})
        source = directory / "graph.osm.pbf"
        source.symlink_to(PBF)
        blocked_ids = sorted(set(blocked_ids))
        if any(not value.isdecimal() or value.startswith("0") for value in blocked_ids):
            raise ValueError("Invalid OSM way ID in the frozen update")
        blocked_lua = "return {" + ",".join('["' + value + '"]=true' for value in blocked_ids) + "}\n"
        (directory / "blocks.lua").write_text(blocked_lua)
        export = directory / "eligible-ways.txt"
        profile = directory / "routing.lua"
        profile.write_text(
            "api_version = 4\n"
            "local car = dofile('/opt/car.lua')\n"
            f"local blocked = dofile('{directory}/blocks.lua')\n"
            "local original = car.process_way\n"
            + (f"local eligible = assert(io.open('{export}', 'a'))\n" if catalog else "")
            + "car.process_way = function(profile, way, result, relations)\n"
            "  local way_id = string.format('%d', way:id())\n"
            "  if blocked[way_id] then return end\n"
            "  original(profile, way, result, relations)\n"
            + ("  if result.forward_mode == mode.driving or result.backward_mode == mode.driving then\n"
               "    eligible:write(way_id .. '\\n'); eligible:flush()\n  end\n" if catalog else "")
            + "end\nreturn car\n"
        )
        deadline = time.monotonic() + PREPARE_TIMEOUT
        log_file = directory / "prepare.log"
        self.run_command(["osrm-extract", "--threads", "1", "-p", str(profile), str(source)], deadline, log_file)
        base = directory / "graph.osrm"
        self.run_command(["osrm-partition", "--threads", "1", str(base)], deadline, log_file)
        self.run_command(["osrm-customize", "--threads", "1", str(base)], deadline, log_file)
        if not graph_exists(base):
            raise RuntimeError("Prepared routing graph is incomplete")
        if dataset_hash() != self.fingerprint:
            self.map_changed = True
            raise ApiError(503, "ROUTING_DATASET_CHANGED", "The source map changed during preparation")
        atomic_json(directory / "manifest.json", {
            "datasetHash": self.fingerprint, "revision": revision,
            "blockedWayIds": blocked_ids,
            "previousBase": str(active_base()) if active_base() else None,
        })
        return base

    def stop_process(self, process):
        if process.poll() is not None:
            return
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            process.wait(timeout=5)
            return
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=5)

    def stop_routed(self):
        if self.routed is not None:
            self.stop_process(self.routed)
        self.routed = None
        self.served_base = None

    def start_routed(self, base):
        base = contained(base)
        if self.routed is not None and self.routed.poll() is None and self.served_base == base and healthy():
            return
        self.stop_routed()
        self.routed = subprocess.Popen([
            "osrm-routed", "--algorithm", "mld", "--ip", "127.0.0.1", "--port", "5002",
            "--threads", "1", "--max-table-size", "1400",
            "--max-viaroute-size", "1002", str(base)
        ], start_new_session=True)
        self.served_base = base
        deadline = time.monotonic() + 60
        while not STOP.is_set() and self.routed.poll() is None and time.monotonic() < deadline:
            if healthy():
                return
            STOP.wait(0.5)
        self.stop_routed()
        raise RuntimeError("The routing graph did not become ready")

    def metadata(self):
        return json.loads(CATALOG.read_text()) if CATALOG.exists() else None

    def normalized_manifest(self, base):
        manifest = read_manifest(base)
        ways = manifest.get("blockedWayIds")
        revision = manifest.get("revision")
        if (not isinstance(ways, list)
                or any(not isinstance(value, str) or not WAY_ID.fullmatch(value) for value in ways)
                or len(set(ways)) != len(ways)
                or type(revision) is not int or not 0 <= revision <= MAX_VERSION
                or manifest.get("datasetHash") != self.fingerprint):
            raise RuntimeError("The published routing manifest is invalid or identifies another map")
        return {"datasetHash": self.fingerprint, "revision": revision, "blockedWayIds": sorted(ways)}

    def import_catalog(self, base):
        eligible = set((base.parent / "eligible-ways.txt").read_text().splitlines())
        if not eligible:
            raise RuntimeError("The car profile exported no selectable roads")
        with connect() as connection:
            connection.execute("SET LOCAL statement_timeout = '15min'")
            count = connection.execute("SELECT count(*) AS count FROM routing.road_segments").fetchone()["count"]
            if count:
                raise RuntimeError("Refusing to replace a nonempty road catalog without reconciliation")
            with connection.cursor().copy(
                    "COPY routing.road_segments (osm_way_id, name, geometry, bounds) FROM STDIN"
            ) as copy:
                importer = CatalogImporter(copy, eligible)
                importer.apply_file(str(PBF), locations=True, idx="flex_mem")
            if importer.imported != eligible:
                raise RuntimeError("Some routable ways could not be included in the road catalog")
        atomic_json(CATALOG, {"datasetHash": self.fingerprint, "catalogReady": True, "elevationDatasetHash": None})

    def refresh_elevation(self):
        metadata = self.metadata()
        directory = Path(os.environ.get("ROUTING_ELEVATION_ROOT", str(DATA / "elevation")))
        with ElevationSampler(directory) as elevation:
            if metadata.get("elevationDatasetHash") == elevation.fingerprint:
                return
            with connect() as connection:
                connection.execute("SET LOCAL statement_timeout = '15min'")
                with connection.cursor(name="routing_elevation_rows") as rows, connection.cursor() as writer:
                    rows.itersize = 500
                    rows.execute("SELECT osm_way_id, geometry FROM routing.road_segments ORDER BY osm_way_id")
                    batch = []
                    update_sql = """
                        UPDATE routing.road_segments SET elevation_start_m = %s, elevation_end_m = %s,
                            slope_percent = %s, slope_degrees = %s WHERE osm_way_id = %s
                        """
                    for row in rows:
                        if STOP.is_set():
                            raise InterruptedError("Elevation preprocessing was interrupted")
                        batch.append((*elevation.metrics(row["geometry"]["coordinates"]), row["osm_way_id"]))
                        if len(batch) == 500:
                            writer.executemany(update_sql, batch)
                            batch.clear()
                    if batch:
                        writer.executemany(update_sql, batch)
                elevation.verify_unchanged()
            # Si falla esta escritura se recalcula al reiniciar; nunca se marca antes del commit SQL
            metadata["elevationDatasetHash"] = elevation.fingerprint
            atomic_json(CATALOG, metadata)

    def bootstrap_catalog(self, current_base, count):
        if BOOTSTRAP.exists():
            pending = json.loads(BOOTSTRAP.read_text())
            if pending.get("datasetHash") != self.fingerprint:
                raise RuntimeError("The catalog bootstrap belongs to another map")
            prepared = contained(pending["preparedBase"])
            self.normalized_manifest(prepared)
            if not graph_exists(prepared):
                raise RuntimeError("The prepared catalog graph is incomplete")
        else:
            name = "catalog-" + str(uuid.uuid4())
            try:
                prepared = self.prepare_graph(name, [], 0, catalog=True)
            except Exception:
                self.remove_unpublished(VERSIONS / name)
                raise
            pending = {"datasetHash": self.fingerprint, "preparedBase": str(prepared),
                       "needsPublish": current_base is None or not (current_base.parent / "manifest.json").exists()}
            # Esta referencia antecede al commit SQL para recuperar tambien la perdida de su confirmacion
            atomic_json(BOOTSTRAP, pending)
        if count == 0:
            self.import_catalog(prepared)
        else:
            expected = set((prepared.parent / "eligible-ways.txt").read_text().splitlines())
            with connect() as connection:
                actual = {row["osm_way_id"] for row in connection.execute("SELECT osm_way_id FROM routing.road_segments")}
            if actual != expected:
                raise RuntimeError("The imported catalog differs from its durable bootstrap reference")
            if self.metadata() is None:
                atomic_json(CATALOG, {"datasetHash": self.fingerprint, "catalogReady": True,
                                      "elevationDatasetHash": None})
        if pending["needsPublish"]:
            self.start_routed(prepared)
            set_active(prepared)
            current_base = prepared
        BOOTSTRAP.unlink()
        sync_directory(DATA)
        return current_base, self.metadata()

    def initialize(self):
        self.fingerprint = dataset_hash()
        self.source_stamp = (PBF.stat().st_size, PBF.stat().st_mtime_ns)
        metadata = self.metadata()
        if metadata is not None and metadata["datasetHash"] != self.fingerprint:
            self.map_changed = True
            raise RuntimeError("Map changed; reconcile the road catalog before activation")
        with connect() as connection:
            count = connection.execute("SELECT count(*) AS count FROM routing.road_segments").fetchone()["count"]
        base = active_base()
        if count == 0 or BOOTSTRAP.exists():
            base, metadata = self.bootstrap_catalog(base, count)
        if base is None:
            raise RuntimeError("The confirmed routing graph is missing")
        manifest = self.normalized_manifest(base)
        if metadata is None:
            # Un indice sin identidad verificable no se asocia automaticamente a otro mapa
            raise RuntimeError("Road catalog metadata is missing; reconciliation is required")
        self.start_routed(base)
        self.manifest = manifest
        self.catalog_ready = True
        self.map_changed = False
        self.initialized = True
        self.switching = False
        self.available = True
        if JOURNAL.exists():
            # El enlace publicado es la decision durable; un candidato no publicado nunca reemplaza al activo
            JOURNAL.unlink()
            sync_directory(DATA)
        try:
            self.refresh_elevation()
        except (OSError, RuntimeError, ValueError) as exception:
            LOG.warning("Visual elevation unchanged: %s", type(exception).__name__)
        self.prune_versions(base, read_manifest(base).get("previousBase"))

    def active_state(self):
        with self.condition:
            if not self.initialized or self.manifest is None:
                raise ApiError(503, "ROUTING_CATALOG_NOT_READY", "The confirmed routing graph is not ready")
            live = self.routed is not None and self.routed.poll() is None
            return {"version": self.manifest["revision"], "wayIds": self.manifest["blockedWayIds"],
                    "available": self.available and live and not self.switching,
                    "saving": self.saving, "catalogReady": self.catalog_ready,
                    "mapChanged": self.map_changed, "datasetHash": self.fingerprint}

    def validate_save(self, body):
        if (not isinstance(body, dict) or set(body) != {"version", "wayIds"}
                or type(body["version"]) is not int or not 0 <= body["version"] <= MAX_VERSION
                or not isinstance(body["wayIds"], list) or len(body["wayIds"]) > 1000
                or any(not isinstance(value, str) or not WAY_ID.fullmatch(value) for value in body["wayIds"])
                or len(set(body["wayIds"])) != len(body["wayIds"])):
            raise ApiError(400, "VALIDATION_ERROR", "Provide a version and up to 1000 distinct OSM way IDs")
        return sorted(body["wayIds"])

    def save(self, body):
        ways = self.validate_save(body)
        if not self.initialized:
            raise ApiError(503, "ROUTING_CATALOG_NOT_READY", "The confirmed routing graph is not ready")
        if not self.save_lock.acquire(blocking=False):
            if not self.saving:
                raise ApiError(503, "ROUTING_COORDINATOR_UNAVAILABLE", "The coordinator is recovering or initializing")
            raise ApiError(409, "ROUTING_SAVE_IN_PROGRESS", "Another save is in progress")
        with self.condition:
            self.saving = True
        candidate = None
        candidate_directory = None
        try:
            state = self.active_state()
            if self.map_changed:
                raise ApiError(503, "ROUTING_DATASET_CHANGED", "The source map changed")
            if not state["available"]:
                raise ApiError(503, "ROUTING_COORDINATOR_UNAVAILABLE", "The confirmed graph is unavailable")
            if ways == self.manifest["blockedWayIds"]:
                return {"version": self.manifest["revision"]}
            if body["version"] != self.manifest["revision"]:
                raise ApiError(409, "ROUTING_VERSION_CONFLICT", "Reload the current blocks before saving")
            if self.manifest["revision"] == MAX_VERSION:
                raise ApiError(503, "ROUTING_VERSION_LIMIT", "The routing version limit was reached")
            if ways:
                with connect() as connection:
                    count = connection.execute("SELECT count(*) AS count FROM routing.road_segments WHERE osm_way_id = ANY(%s)",
                                               (ways,)).fetchone()["count"]
                if count != len(ways):
                    raise ApiError(400, "ROUTING_WAY_NOT_FOUND", "A selected OSM way does not exist")
            try:
                name = "save-" + str(uuid.uuid4())
                candidate_directory = VERSIONS / name
                candidate = self.prepare_graph(name, ways, self.manifest["revision"] + 1)
            except ApiError:
                raise
            except Exception as exception:
                LOG.error("Graph preparation failed: %s", type(exception).__name__)
                raise ApiError(503, "ROUTING_PREPARATION_FAILED", "The previous blocks remain effective") from exception
            self.activate(candidate)
            return {"version": self.manifest["revision"]}
        finally:
            try:
                if candidate_directory is not None:
                    self.remove_unpublished(candidate_directory)
            except (OSError, RuntimeError, ValueError):
                LOG.warning("Deferred cleanup after save")
            with self.condition:
                self.saving = False
                self.condition.notify_all()
            self.save_lock.release()

    def activate(self, candidate):
        manifest = self.normalized_manifest(candidate)
        previous = active_base()
        with self.condition:
            self.switching = True
            deadline = time.monotonic() + 120
            while self.proxy_requests and time.monotonic() < deadline and not STOP.is_set():
                self.condition.wait(timeout=0.5)
            if self.proxy_requests or STOP.is_set():
                self.switching = False
                raise ApiError(503, "ROUTING_ACTIVATION_FAILED", "The previous blocks remain effective")
            self.available = False
        try:
            atomic_json(JOURNAL, {"format": "routing-effective-v2", "newBase": str(candidate),
                                 "previousBase": str(previous) if previous else None})
            self.stop_routed()
            self.start_routed(candidate)
            # Este reemplazo publica a la vez el grafo y el manifiesto que contiene su lista efectiva
            set_active(candidate)
            with self.condition:
                self.manifest = manifest
                self.available = True
                self.switching = False
        except Exception as exception:
            if active_base() == candidate:
                # El commit pudo completarse antes de perderse una confirmacion local; no volver atras silenciosamente
                self.initialized = False
                raise ApiError(503, "ROUTING_SAVE_RESULT_UNKNOWN", "Reload the effective blocks to confirm the save result") from exception
            try:
                self.start_routed(previous)
                with self.condition:
                    self.available = True
                    self.switching = False
                JOURNAL.unlink(missing_ok=True)
                sync_directory(DATA)
            except Exception:
                self.initialized = False
                self.available = False
            raise ApiError(503, "ROUTING_ACTIVATION_FAILED", "The save failed; consult routing availability") from exception
        try:
            JOURNAL.unlink(missing_ok=True)
            sync_directory(DATA)
            self.prune_versions(candidate, previous)
        except OSError:
            LOG.warning("The new graph is confirmed; deferred file cleanup remains")

    def remove_unpublished(self, directory, extra_protected=()):
        if Path(directory).is_symlink():
            return
        directory = contained(directory)
        if directory.parent != VERSIONS or not directory.is_dir():
            return
        try:
            marker = json.loads((directory / ".routing-owned.json").read_text())
            if marker != {"format": "routing-version-v1", "name": directory.name}:
                return
            protected = {contained(path).parent for path in extra_protected if path}
            current = active_base()
            if current:
                protected.add(contained(current).parent)
                previous = read_manifest(current).get("previousBase") if (current.parent / "manifest.json").exists() else None
                if previous:
                    protected.add(contained(previous).parent)
            if self.served_base:
                protected.add(contained(self.served_base).parent)
            if JOURNAL.exists():
                journal = json.loads(JOURNAL.read_text())
                protected.update(contained(journal[key]).parent for key in ("newBase", "previousBase") if journal.get(key))
            if BOOTSTRAP.exists():
                protected.add(contained(json.loads(BOOTSTRAP.read_text())["preparedBase"]).parent)
            if directory not in protected:
                shutil.rmtree(directory)
        except (OSError, ValueError, KeyError, RuntimeError):
            LOG.warning("Deferred cleanup of an unconfirmed version directory")

    def prune_versions(self, active, previous):
        for directory in VERSIONS.iterdir():
            self.remove_unpublished(directory, (active, previous))

    def proxy(self, handler):
        with self.condition:
            if not self.initialized or not self.available or self.switching or self.map_changed:
                handler.close_connection = True
                handler.json_response(503, {"code": "NoRoute", "message": "Routing is temporarily unavailable"})
                return
            self.proxy_requests += 1
        connection = http.client.HTTPConnection("127.0.0.1", 5002, timeout=180)
        response_sent = False
        try:
            body = handler.read_body()
            headers = {key: value for key, value in handler.headers.items()
                       if key.lower() not in HOP_HEADERS and key.lower() not in {"host", "authorization", "cookie"}}
            connection.request(handler.command, handler.path, body=body, headers=headers)
            response = connection.getresponse()
            payload = response.read()
            handler.send_response(response.status)
            for key, value in response.getheaders():
                if key.lower() not in HOP_HEADERS:
                    handler.send_header(key, value)
            handler.send_header("Content-Length", str(len(payload)))
            handler.end_headers()
            response_sent = True
            handler.wfile.write(payload)
        except (OSError, http.client.HTTPException):
            handler.close_connection = True
            if not response_sent:
                handler.json_response(503, {"code": "NoRoute", "message": "Routing is temporarily unavailable"})
        finally:
            connection.close()
            with self.condition:
                self.proxy_requests -= 1
                self.condition.notify_all()

    def run(self):
        DATA.mkdir(parents=True, exist_ok=True)
        VERSIONS.mkdir(exist_ok=True)
        lock = (DATA / "routing-coordinator.lock").open("a")
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        servers = []
        for port, handler in ((5000, RoutingProxyHandler), (5001, ManagementHandler)):
            server = ThreadingHTTPServer(("0.0.0.0", port), handler)
            server.controller = self
            servers.append(server)
            threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            while not STOP.is_set():
                if self.save_lock.acquire(blocking=False):
                    try:
                        if not self.initialized:
                            self.initialize()
                        stamp = (PBF.stat().st_size, PBF.stat().st_mtime_ns)
                        if stamp != self.source_stamp:
                            self.map_changed = True
                            self.available = False
                        if not self.map_changed:
                            live = self.routed is not None and self.routed.poll() is None
                            with self.condition:
                                busy = self.proxy_requests > 0
                            # Un nearest lento con table en curso no demuestra que el proceso este roto
                            needs_restart = not live or (not busy and not healthy())
                            if needs_restart:
                                with self.condition:
                                    # Una consulta pudo comenzar mientras se hacia el probe
                                    can_restart = not live or self.proxy_requests == 0
                                    if can_restart:
                                        self.available = False
                                        self.switching = True
                                if can_restart:
                                    self.start_routed(active_base())
                                    with self.condition:
                                        self.available = True
                                        self.switching = False
                    except (psycopg.Error, OSError, RuntimeError, ValueError) as exception:
                        self.initialized = False
                        self.available = False
                        self.switching = True
                        LOG.warning("Routing recovery pending: %s", type(exception).__name__)
                    finally:
                        self.save_lock.release()
                STOP.wait(2)
        finally:
            STOP.set()
            self.available = False
            for server in servers:
                server.shutdown()
                server.server_close()
            self.stop_routed()
            lock.close()


class JsonHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def setup(self):
        super().setup()
        self.connection.settimeout(180)

    def log_message(self, format, *args):
        return

    def read_body(self):
        if self.headers.get("Transfer-Encoding"):
            raise ApiError(400, "VALIDATION_ERROR", "Chunked requests are not supported")
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exception:
            raise ApiError(400, "VALIDATION_ERROR", "Invalid body length") from exception
        if not 0 <= length <= 2097152:
            raise ApiError(400, "VALIDATION_ERROR", "Request body is too large")
        return self.rfile.read(length) if length else None

    def json_response(self, status, body):
        payload = json.dumps(body, allow_nan=False).encode()
        if status >= 400:
            self.close_connection = True
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(payload)
        except OSError:
            self.close_connection = True


    def png_response(self, payload):
        self.send_response(200)
        self.send_header("Content-Type", "image/png")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "private, max-age=300")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        try:
            self.wfile.write(payload)
        except OSError:
            self.close_connection = True


class ManagementHandler(JsonHandler):
    def handle_request(self):
        controller = self.server.controller
        if not hmac.compare_digest(self.headers.get("X-Routing-Token", "").encode(), controller.token.encode()):
            self.close_connection = True
            self.json_response(403, {"code": "FORBIDDEN", "detail": "Invalid coordinator credentials"})
            return
        tile = re.fullmatch(r"/elevation/tiles/([0-9]{1,2})/([0-9]{1,7})/([0-9]{1,7})\.png", self.path)
        if tile is not None and self.command == "GET":
            zoom, x, y = map(int, tile.groups())
            if not 0 <= zoom <= 16 or not 0 <= x < (1 << zoom) or not 0 <= y < (1 << zoom):
                self.json_response(400, {"code": "VALIDATION_ERROR", "detail": "Invalid XYZ tile coordinates"})
                return
            try:
                self.png_response(controller.elevation_tiles.tile(zoom, x, y))
            except FileNotFoundError:
                self.json_response(503, {"code": "ROUTING_ELEVATION_NOT_READY",
                                         "detail": "The local elevation rasters are not available"})
            except Exception as exception:
                LOG.warning("Elevation tile unavailable: %s", type(exception).__name__)
                self.json_response(503, {"code": "ROUTING_ELEVATION_UNAVAILABLE",
                                         "detail": "The elevation layer is temporarily unavailable"})
            return
        if self.path != "/active-blocks":
            self.json_response(404, {"code": "NOT_FOUND", "detail": "Unknown coordinator operation"})
            return
        try:
            if self.command == "GET":
                result = controller.active_state()
            else:
                try:
                    body = json.loads(self.read_body() or b"null")
                except (ValueError, UnicodeDecodeError) as exception:
                    raise ApiError(400, "MALFORMED_REQUEST", "The body could not be parsed") from exception
                result = controller.save(body)
            self.json_response(200, result)
        except ApiError as exception:
            self.json_response(exception.status, {"code": exception.code, "detail": exception.detail})
        except Exception as exception:
            LOG.error("Coordinator request failed: %s", type(exception).__name__)
            self.json_response(503, {"code": "ROUTING_COORDINATOR_UNAVAILABLE", "detail": "The coordinator is unavailable"})

    do_GET = handle_request
    do_PUT = handle_request


class RoutingProxyHandler(JsonHandler):
    def handle_request(self):
        if not re.match(r"^/(route|table|nearest|match|trip|tile)/v1/", self.path):
            self.json_response(404, {"code": "InvalidUrl", "message": "Unknown OSRM operation"})
            return
        try:
            self.server.controller.proxy(self)
        except ApiError as exception:
            self.json_response(exception.status, {"code": "InvalidQuery", "message": exception.detail})

    do_GET = handle_request
    do_POST = handle_request


def handle_signal(signum, frame):
    STOP.set()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)
    Coordinator().run()

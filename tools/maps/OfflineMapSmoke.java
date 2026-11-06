package com.mercaforte.offlinetest;

import android.app.Activity;
import android.app.Instrumentation;
import android.graphics.Bitmap;
import android.os.Bundle;
import java.io.File;
import java.io.FileOutputStream;
import java.util.HashSet;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;
import org.maplibre.android.MapLibre;
import org.maplibre.android.camera.CameraPosition;
import org.maplibre.android.geometry.LatLng;
import org.maplibre.android.snapshotter.MapSnapshotter;

/** Instrumentación externa: renderiza los assets del APK sin login, rutas ni Metro. */
public class OfflineMapSmoke extends Instrumentation {
    @Override public void onCreate(Bundle arguments) { super.onCreate(arguments); start(); }

    @Override public void onStart() {
        Bundle result = new Bundle();
        try {
            runOnMainSync(() -> { MapLibre.getInstance(getTargetContext()); MapLibre.setConnected(false); });
            String[] names = {"Cuernavaca", "Jiutepec", "Yautepec", "Emiliano Zapata", "Temixco", "Xochitepec",
                "Huitzilac", "Tepoztlán", "Toluca (excluida)", "Ciudad de México (excluida)"};
            double[][] centers = {{18.924, -99.234}, {18.884, -99.177}, {18.882, -99.067},
                {18.840, -99.185}, {18.852, -99.226}, {18.781, -99.230},
                {19.029, -99.268}, {18.986, -99.101}, {19.283, -99.656}, {19.433, -99.133}};
            File directory = new File(getTargetContext().getCacheDir(), "offline-map-smoke");
            if (!directory.isDirectory() && !directory.mkdirs()) throw new IllegalStateException("No se pudo crear el directorio de capturas");
            for (int i = 0; i < names.length; i++) {
                final int index = i;
                CountDownLatch done = new CountDownLatch(1);
                AtomicReference<Bitmap> image = new AtomicReference<>();
                AtomicReference<String> error = new AtomicReference<>();
                AtomicReference<MapSnapshotter> renderer = new AtomicReference<>();
                runOnMainSync(() -> {
                    CameraPosition camera = new CameraPosition.Builder()
                        .target(new LatLng(centers[index][0], centers[index][1])).zoom(13.5).build();
                    MapSnapshotter snapshotter = new MapSnapshotter(getTargetContext(),
                        new MapSnapshotter.Options(640, 640).withStyle("asset://maps/morelos-centro/style.json")
                            .withCameraPosition(camera).withLogo(false).withAttribution(index < 8));
                    renderer.set(snapshotter);
                    snapshotter.start(snapshot -> { image.set(snapshot.getBitmap()); done.countDown(); },
                        message -> { error.set(message); done.countDown(); });
                });
                if (!done.await(30, TimeUnit.SECONDS)) throw new IllegalStateException("Timeout: " + names[i]);
                if (error.get() != null) throw new IllegalStateException(names[i] + ": " + error.get());
                Bitmap bitmap = image.get();
                if (bitmap == null) throw new IllegalStateException("Sin imagen: " + names[i]);
                HashSet<Integer> colors = new HashSet<>();
                for (int y = 0; y < bitmap.getHeight(); y += 3)
                    for (int x = 0; x < bitmap.getWidth(); x += 3) colors.add(bitmap.getPixel(x, y));
                if (i < 8 && colors.size() < 128) throw new IllegalStateException("Cartografía vacía: " + names[i]);
                if (i >= 8 && colors.size() > 8) throw new IllegalStateException("Cartografía externa incluida: " + names[i]);
                try (FileOutputStream out = new FileOutputStream(new File(directory, "municipality-" + i + ".png"))) {
                    bitmap.compress(Bitmap.CompressFormat.PNG, 100, out);
                }
                Bundle progress = new Bundle();
                progress.putString("stream", names[i] + ": " + (i < 8 ? "mapa local renderizado" : "sin cartografía externa")
                    + "; " + colors.size() + " colores\n");
                sendStatus(0, progress);
                runOnMainSync(() -> renderer.get().cancel());
            }
            result.putString("stream", "OK: ocho municipios renderizados sin red ni Metro; Toluca y CDMX excluidos.\n");
            finish(Activity.RESULT_OK, result);
        } catch (Throwable error) {
            result.putString("stream", "ERROR: " + error.toString() + "\n");
            finish(Activity.RESULT_CANCELED, result);
        }
    }
}

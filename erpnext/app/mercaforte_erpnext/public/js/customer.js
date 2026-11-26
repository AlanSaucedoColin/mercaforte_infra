(() => {
	const estado = "custom_mercaforte_estado";
	const municipio = "custom_mercaforte_municipio";
	const latitud = "custom_mercaforte_latitud";
	const longitud = "custom_mercaforte_longitud";
	const abrir_mapa = "custom_mercaforte_abrir_mapa";
	// INEGI municipal seats, indexed by the municipality code stored on Customer.
	const cabeceras_morelos = {
		"17001": [18.6000017, -99.3695142],
		"17002": [18.9362708, -98.8991753],
		"17003": [18.5024064, -98.7540786],
		"17004": [18.7670867, -98.9821417],
		"17005": [18.7441856, -99.4348006],
		"17006": [18.8127883, -98.9552647],
		"17007": [18.9217828, -99.2348969],
		"17008": [18.8409842, -99.1832428],
		"17009": [19.0290331, -99.2674528],
		"17010": [18.7152058, -98.7773008],
		"17011": [18.8819744, -99.1771983],
		"17012": [18.6165664, -99.1810436],
		"17013": [18.6806903, -98.8032231],
		"17014": [18.7331844, -99.3669719],
		"17015": [18.7699825, -99.3602653],
		"17016": [18.8776928, -98.7756975],
		"17017": [18.616875, -99.3237014],
		"17018": [18.8452733, -99.2241431],
		"17019": [18.5947364, -98.8443567],
		"17020": [18.9864572, -99.1012269],
		"17021": [18.7289672, -99.3985831],
		"17022": [18.893525, -98.7300656],
		"17023": [19.0079269, -98.9973522],
		"17024": [18.6829622, -99.1181789],
		"17025": [18.63003, -99.1626622],
		"17026": [18.9566172, -98.9831175],
		"17027": [18.9872233, -98.9214389],
		"17028": [18.7818656, -99.2314628],
		"17029": [18.8860617, -99.0607542],
		"17030": [18.8834197, -98.8681436],
		"17031": [18.6554081, -99.1942789],
		"17032": [18.7843931, -98.7654231],
		"17033": [18.772315, -98.7780431],
		"17034": [18.7304858, -99.3270575],
		"17035": [18.6865728, -99.2448947],
		"17036": [18.8851344, -98.6906842],
	};
	const cuernavaca = cabeceras_morelos["17007"];
	let picker;

	function make_picker() {
		let editable = false;
		let marker;
		const dialog = new frappe.ui.Dialog({
			title: __("Ubicación de la tienda"),
			size: "large",
			fields: [
				{ fieldname: "mapa", fieldtype: "Geolocation", label: __("Mapa") },
				{
					fieldname: "borrar", fieldtype: "Button", label: __("Borrar ubicación"),
					click: () => set_marker(null),
				},
			],
		});
		const field = dialog.get_field("mapa");
		// Geolocation listens for every dialog's shown event. Reuse one control
		// and initialize it only when its own dialog is visible.
		const make_map = field.make_map.bind(field);
		field.make_map = () => {
			if (dialog.display && !field.map) make_map();
		};
		field.bind_leaflet_draw_control = () => {};
		field.bind_leaflet_locate_control = () => {};
		field.bind_leaflet_event_listeners = function () {
			this.bound_event_listeners = true;
			this.map.options.zoomSnap = 0;
			L.control.scale({ imperial: false }).addTo(this.map);
			this.map.on("click", ({ latlng }) => {
				if (editable) set_marker(latlng.wrap());
			});
		};

		function set_marker(point) {
			marker?.remove();
			marker = point ? L.marker(point, { draggable: editable }).addTo(field.map) : null;
			dialog.get_field("borrar").toggle(editable && Boolean(marker));
		}

		dialog.on_hide = () => {
			set_marker(null);
			field.map?.setView(cuernavaca, field.map.getZoom(), { animate: false });
		};

		return (frm, doc, can_edit) => {
			editable = can_edit;
			dialog.on_page_show = () => {
				field.make_map();
				const lat = Number(doc[latitud]) || 0;
				const lng = Number(doc[longitud]) || 0;
				const point = lat || lng ? [lat, lng] : null;
				set_marker(point);
				field.map.invalidateSize();
				const center = L.latLng(point || cabeceras_morelos[doc[municipio]] || cuernavaca);
				const bounds = center.toBounds(2000);
				// Fit the horizontal span independently of the dialog's aspect ratio.
				const width = L.latLngBounds([center.lat, bounds.getWest()], [center.lat, bounds.getEast()]);
				field.map.setView(center, field.map.getBoundsZoom(width), { animate: false });
			};
			dialog.set_secondary_action_label(__("Cancelar"));
			dialog.set_secondary_action(() => dialog.hide()).toggle(editable);
			dialog.set_primary_action(editable ? __("Aplicar ubicación") : __("Cerrar"), async () => {
				if (editable && frm.doc === doc && cur_frm === frm) {
					const point = marker?.getLatLng().wrap();
					await frm.set_value({
						[latitud]: flt(point?.lat, frm.get_field(latitud).get_precision()),
						[longitud]: flt(point?.lng, frm.get_field(longitud).get_precision()),
					});
				}
				dialog.hide();
			});
			dialog.show();
		};
	}

	async function open_map(frm) {
		const doc = frm.doc;
		await frappe.require(["leaflet.bundle.js", "leaflet.bundle.css"]);
		if (cur_frm !== frm || frm.doc !== doc) return;
		const can_edit = !frm.read_only && !frappe.boot.read_only &&
			[latitud, longitud].every((name) => frm.get_field(name).get_status() === "Write");
		picker ??= make_picker();
		picker(frm, doc, can_edit);
	}

	frappe.ui.form.on("Customer", {
		setup(frm) {
			const control = frm.get_field(municipio);
			if (control) {
				mercaforte_erpnext.customer_location.configure_municipio(control, () => frm.doc[estado]);
			}
		},
		refresh(frm) {
			const statuses = [latitud, longitud].map((name) => frm.get_field(name)?.get_status());
			frm.set_df_property(abrir_mapa, "icon", "map-pin");
			frm.toggle_display(abrir_mapa, statuses.every((status) => status === "Read" || status === "Write"));
		},
		[abrir_mapa]: open_map,
		[estado](frm) {
			const control = frm.get_field(municipio);
			if (!control) return;
			return mercaforte_erpnext.customer_location.estado_changed(
				control,
				frm.doc[estado],
				frm.doc[municipio],
				() => frm.set_value(municipio, "")
			);
		},
	});
})();

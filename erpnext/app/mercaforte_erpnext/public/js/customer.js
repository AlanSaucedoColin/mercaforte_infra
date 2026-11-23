(() => {
	const estado = "custom_mercaforte_estado";
	const municipio = "custom_mercaforte_municipio";
	const ubicacion = "custom_mercaforte_ubicacion";
	const mexico = [23.6345, -102.5528];

	function configure_map(frm, field) {
		const can_edit = () => field.get_status() === "Write" && !field.disabled;
		const save_point = (latlng) => {
			if (!can_edit()) return;
			const point = L.marker(latlng.wrap()).toGeoJSON(false);
			return frm.set_value(ubicacion, JSON.stringify({
				type: "FeatureCollection",
				features: [point],
			}));
		};

		// Use the native Geolocation control and its Leaflet layers. Only this
		// field gets a single manual marker in place of shape and GPS controls.
		field.bind_leaflet_locate_control = () => {};
		field.bind_leaflet_draw_control = () => {};
		field.bind_leaflet_event_listeners = function () {
			this.bound_event_listeners = true;
			this.map.on("click", (event) => save_point(event.latlng));
		};
		field.point_to_layer = (_feature, latlng) => {
			const marker = L.marker(latlng, { draggable: can_edit() });
			marker.on("dragend", () => save_point(marker.getLatLng()));
			return marker;
		};

		field.fit_and_recenter_map = function () {
			if (!this.map) return;
			this.map.invalidateSize();
			const point = this.editableLayers.getLayers()[0];
			this.map.setView(point ? point.getLatLng() : mexico, point ? 15 : 5);
		};

		let last_customer;
		let clear_button;
		const make_map = field.make_map.bind(field);
		field.make_map = function () {
			make_map();
			if (!clear_button) {
				clear_button = $('<button type="button" class="btn btn-xs btn-default mt-2">')
					.text(__("Borrar ubicación"))
					.insertAfter(this.map_area)
					.on("click", () => can_edit() && frm.set_value(ubicacion, ""));
			}
			// The same control instance is reused as Desk navigates between customers.
			const has_marker = this.editableLayers.getLayers().length > 0;
			if (!frm.doc[ubicacion] && (last_customer !== frm.doc.name || has_marker)) {
				this.clear_editable_layers();
				this.fit_and_recenter_map();
			}
			last_customer = frm.doc.name;
			clear_button.toggle(can_edit() && Boolean(frm.doc[ubicacion]));
		};

		// An earlier asynchronous Leaflet load may finish after switching customers.
		const bind_data = field.bind_leaflet_data.bind(field);
		field.bind_leaflet_data = (value) => {
			if (value === frm.doc[ubicacion]) bind_data(value);
		};
	}

	frappe.ui.form.on("Customer", {
		setup(frm) {
			const control = frm.get_field(municipio);
			if (control) {
				mercaforte_erpnext.customer_location.configure_municipio(control, () => frm.doc[estado]);
			}
			const map = frm.get_field(ubicacion);
			if (map) configure_map(frm, map);
		},
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

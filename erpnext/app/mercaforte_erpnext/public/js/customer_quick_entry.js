frappe.provide("mercaforte_erpnext.customer_location");

(() => {
	const estado = "custom_mercaforte_estado";
	const municipio = "custom_mercaforte_municipio";

	function configure_municipio(control, get_estado) {
		control.get_query = () => ({ filters: { estado: get_estado() || "00" } });
		if (control instanceof frappe.ui.form.ControlLinkCombobox) return;

		// Classic Link can receive a previous state's search after the state changed.
		// INEGI's first two municipality digits always identify its state.
		const merge_duplicates = control.merge_duplicates.bind(control);
		control.merge_duplicates = (rows) => {
			const prefix = get_estado();
			return merge_duplicates(rows.filter((row) => prefix && row.value.startsWith(prefix)));
		};
	}

	function estado_changed(control, estado_value, municipio_value, clear_municipio) {
		if (control.combobox?.is_open) control.combobox.close("escape");
		if (control.$input?.cache) control.$input.cache = {};
		if (control.awesomplete) {
			control.awesomplete.list = [];
			control.awesomplete.close();
		}
		if (municipio_value && (!estado_value || !municipio_value.startsWith(estado_value))) {
			return clear_municipio();
		}
	}

	Object.assign(mercaforte_erpnext.customer_location, { configure_municipio, estado_changed });

	// ERPNext supplies the address/contact fields and the native Edit Full Form action.
	frappe.ui.form.CustomerQuickEntryForm = class extends frappe.ui.form.CustomerQuickEntryForm {
		render_dialog() {
			super.render_dialog();
			const state = this.fields_dict[estado];
			const town = this.fields_dict[municipio];
			if (!state || !town) return;

			configure_municipio(town, () => this.doc[estado]);
			// Keep the existing Link control callbacks. The dialog can replace
			// DocField metadata while refreshing, so bind to this control instance.
			const after_set_value = state.after_set_value.bind(state);
			state.after_set_value = () => {
				after_set_value();
				this.refresh_dependency();
				return estado_changed(town, this.doc[estado], this.doc[municipio],
					() => this.set_value(municipio, ""));
			};
		}
	};
})();

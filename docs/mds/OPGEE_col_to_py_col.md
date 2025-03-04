|OPGEE Excel cols|opgee/etc/attributes.xml|Excel v3 Type|Description|
|:---------------|:-----------------------|:---------|:----------|
|Function unit|Functional unit|option|oil or gas|
|Downhole pump|downhole_pump|binary||
|Water reinjection|water_reinjection|binary||
|Natural gas reinjection|natural_gas_reinjection|binary||
|Water flooding|water_flooding|binary||
|Gas lifting|gas_lifting|binary||
|Gas flooding|gas_flooding|binary||
|Steam flooding|steam_flooding|binary||
|Oil sands mine (integrated with upgrader)|oil_sands_mine_type|binary|v4 has subtype for|Integrated with upgrader||
|Oil sands mine (non-integrated with upgrader)|oil_sands_mine_type|binary|v4 has subtype for|Integrated with diluent|| if both are turned on, can choose option for |Integrated with both||
|Field location(Country)|country|str||
|Field name|name|str|depth|
|Field age|age|float|v3 use age as year;former Pyxis record year 19xx and use current year to convert|
|Field depth|depth|float||
|Oil production volume|oil_prod|float||
|Number of producing wells|num_prod_wells|float||
|Number of water injecting wells|num_water_inj_wells|float||
|Production tubing diameter|well_diam|float||
|Productivity index|prod_index|float||
|Reservoir pressure|res_press|float||
|Reservoir temperature|res_temp|float||
|Offshore?|offshore|binary||
|API gravity (oil at standard pressure and temperature, or \|dead oil\|)|API|float||
|N2|gas_comp_N2|float|
|CO2|gas_comp_CO2|float||
|C1|gas_comp_C1|float||
|C2|gas_comp_C2|float||
|C3|gas_comp_C3|float||
|C4+|gas_comp_C4|float||
|H2S|gas_comp_H2S|float||
|Gas-to-oil ratio (GOR)|GOR|float||
|Water-to-oil ratio (WOR)|WOR|float||
|Water injection ratio|WIR|float||
|Gas lifting injection ratio|GLIR|float||
|Gas flooding injection ratio|GFIR|float||
|Flood gas|flood_gases|option|v3 use 1-3 for NG,N2,CO2 in v4|
|Fraction of CO2 breaking through to producers|frac_CO2_breakthrough|float||
|Source of makeup CO2|CO2_source_options|option|v3 use 1-2 for Natural subsurface reservoir, Anthropogenic in v4|
|Percentage of sequestration credit assigned to the oilfield|perc_sequestration_credit|float||
|Steam-to-oil ratio (SOR)|SOR|float||
|Fraction of required fossil electricity generated onsite|fraction_elec_onsite|float||
|Fraction of remaining natural gas reinjected|fraction_remaining_gas_inj|float||
|Fraction of produced water reinjected|fraction_water_reinjected|float||
|Fraction of steam generation via cogeneration|fraction_steam_cogen|float||
|Fraction of steam generation via solar thermal|fraction_steam_solar|float||
|Heater/treater|heater_treater|binary||
|Stabilizer column|stabilizer_column|binary||
|Upgrader type|upgrader_type|option|v3 use 0,1,2,3 for v4 options|
|Associated Gas Processing Path|gas_processing_path|option|v3 use 1-8 for v4 options|
|Flaring-to-oil ratio|FOR|float||
|Purposeful venting fraction (post-flare gas fraction vented)|frac_venting|float||
|Volume fraction of diluent|fraction_diluent|float||
|Low carbon richness (semi-arid grasslands)|ecosystem_C_richness|binary|v4 use ecosystem_C_richness for 3 options|
|Moderate carbon richness (mixed)|ecosystem_C_richness|binary|v4 use ecosystem_C_richness for 3 options|
|High carbon richness (forested)|ecosystem_C_richness|binary|v4 use ecosystem_C_richness for 3 options|
|Low intensity development and low oxidation|field_development_intensity|binary|v4 use field_development_intensity for 3 options|
|Moderate intensity development and moderate oxidation|field_development_intensity|binary|v4 use field_development_intensity for 3 options|
|High intensity development and high oxidation|field_development_intensity|binary|v4 use field_development_intensity for 3 options|
|Ocean tanker_frac|frac_transport_tanker|float|v3 uses Ocean tanker twice, here _frac to distinguish them|
|Barge_frac|frac_transport_barge|float|similarly|
|Pipeline_frac|frac_transport_pipeline|float|similarly|
|Rail_frac|frac_transport_rail|float|similarly|
|Truck_frac|frac_transport_truck|float|similarly|
|Ocean tanker_dis|transport_dist_tanker|float|v3 uses Ocean tanker twice, here _dis to distinguish them|
|Barge_dis|transport_dist_barge|float|similarly|
|Pipeline_dis|transport_dist_pipeline|float|similarly|
|Rail_dis|transport_dist_rail|float|similarly|
|Truck_dis|transport_dist_truck|float|similarly|
|Ocean tanker size, if applicable|ocean_tanker_size|float||
|Small sources emissions||float|
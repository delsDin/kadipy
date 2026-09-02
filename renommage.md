# Renommage - kadipy

Chaque élément actuel (classe, méthode, attribut) est mis en regard de sa
proposition améliorée. Les conventions retenues s'inspirent de Pandas et de
l'écosystème scientifique Python : noms courts, sans préfixe redondant,
entièrement en anglais, lisibles en un coup d'oeil.

Convention : `_` en tête = méthode/attribut interne (inchangé).

---

## 1. Chemins d'importation (modules)

| Chemin actuel | Chemin proposé | Raison |
|---|---|---|
| `kadi.kidas.sources.csv_source` | `kadi.io` (via `__init__`) | Accès direct depuis le niveau `kadi` |
| `kadi.kidas.sources.excel_source` | `kadi.io` | Idem |
| `kadi.kidas.sources.json_source` | `kadi.io` | Idem |
| `kadi.kidas.sources.netcdf_source` | `kadi.io` | Idem |
| `kadi.kidas.sources.api_source` | `kadi.io` | Idem |
| `kadi.kidas.cleaner` | `kadi.kidas` | Exposé directement dans `kadi.kidas` |
| `kadi.kidas.validator` | `kadi.kidas` | Idem |
| `kadi.kidas.normalizer` | `kadi.kidas` | Idem |
| `kadi.kidas.pipeline` | `kadi.kidas` | Idem |
| `kadi.kidas.cache` | `kadi.kidas` | Idem |
| `kadi.weather.session` | `kadi.weather` | `WeatherSession` devient `Weather`, exposé au niveau `kadi` |
| `kadi.market.__init__` | `kadi.market` | `Market` déjà en façade, ok |
| `kadi._sources.exchange_client` | Privé, inchangé | Interne, non public |
| `kadi._sources.wfp_client` | Privé, inchangé | Interne, non public |
| `kadi.market.data_ingestion` | Fusionner dans `kadi._sources.wfp_client` | Doublon à supprimer |

---

## 2. Exceptions — `kadi.exceptions`

| Nom actuel | Nom proposé | Raison |
|---|---|---|
| `KadiException` | `KadiError` | Suffixe `Error` est le standard Python (`ValueError`, `IOError`) |
| `DataSourceError` | `SourceError` | Préfixe `Data` redondant dans ce contexte |
| `CacheError` | `CacheError` | Déjà bon, conservé |
| `ValidationError` | `ValidationError` | Déjà bon, conservé |
| `OfflineError` | `OfflineError` | Déjà bon, conservé |
| `LocationNotFound` | `LocationError` | Plus cohérent avec le suffixe `Error` |
| `CropNotFound` | `CropError` | Idem |
| `InsufficientData` | `DataError` | Plus court et cohérent |
| `KidasReadError` | `ReadError` | Préfixe `Kidas` redondant si dans `kadi.exceptions` |
| `KidasWriteError` | `WriteError` | Idem |
| `KidasConnectionError` | `ConnectionError` | Idem |
| `KidasCleaningError` | `CleanError` | Plus court |
| `KidasValidationError` | Fusionner avec `ValidationError` | Doublon |
| `KidasCacheError` | Fusionner avec `CacheError` | Doublon |
| `KidasPipelineError` | `PipelineError` | Préfixe supprimé |

---

## 3. Sources de données — `kadi.io`

### Classe de base `DataSource`

| Elément actuel | Proposition | Raison |
|---|---|---|
| `DataSource` (classe) | `Source` | Préfixe `Data` redondant, idem Pandas `Index`, `Series` |
| `self.source_path` | `self.path` | Plus court, sans redondance |
| `self.source_type` | `self.kind` | Evite la collision avec `type()` builtin |
| `self.encoding` | inchangé | Déjà clair |
| `self.last_read` | `self.last_read` | Déjà clair |
| `validate_connection()` | `ping()` | Plus court et expressif |
| `_update_last_read()` | `_touch()` | Analogie UNIX, très claire |
| `get_metadata()` | `info()` | Analogie Pandas `df.info()` |

### `CSVDataSource`

| Elément actuel | Proposition | Raison |
|---|---|---|
| `CSVDataSource` (classe) | `CSVSource` | Suppression du suffixe `Data` |
| `self._detected_delimiter` | `self._sep` | Abréviation standard (Pandas utilise `sep=`) |
| `self._detected_encoding` | `self._enc` | Abréviation cohérente |
| `self.decimal` | inchangé | Standard Pandas |
| `self.delimiter` | `self.sep` | Alignement sur Pandas |
| `self.file_path` | `self.path` | Cohérence avec la classe de base |
| `detect_encoding()` | `_sniff_encoding()` | `detect` trop vague, `sniff` est le terme standard |
| `detect_delimiter()` | `_sniff_sep()` | Idem |
| `read(nrows, skip_rows)` | `read(n, skip)` | Paramètres courts, naturels |
| `write(data, index)` | inchangé | Clair |

### `ExcelDataSource`

| Elément actuel | Proposition | Raison |
|---|---|---|
| `ExcelDataSource` (classe) | `ExcelSource` | Suppression de `Data` |
| `self._detected_header_row` | `self._header` | Plus court |
| `self.file_path` | `self.path` | Cohérence |
| `self.header_row` | `self.header` | Plus court |
| `self.sheet_name` | `self.sheet` | Plus court |
| `detect_header_row()` | `_sniff_header()` | Cohérence avec `CSVSource` |
| `list_sheets()` | `sheets()` | Verbe inutile, `df.columns` pas `list_columns()` |
| `get_sheet_metadata(sheet_name)` | `sheet_info(sheet)` | Cohérence avec `info()` |
| `unmerge_cells(df)` | `_unmerge(df)` | Méthode interne, préfixe `_` ajouté |

### `JSONDataSource`

| Elément actuel | Proposition | Raison |
|---|---|---|
| `JSONDataSource` (classe) | `JSONSource` | Suppression de `Data` |
| `self._dict_source` | `self._raw` | Plus générique et court |
| `self.file_path` | `self.path` | Cohérence |
| `flatten_json(json_obj, separateur)` | `flatten(obj, sep)` | Sans redondance avec le nom de la classe |
| `_charger_json_brut()` | `_load_raw()` | En anglais, cohérent |

### `NetCDFDataSource`

| Elément actuel | Proposition | Raison |
|---|---|---|
| `NetCDFDataSource` (classe) | `NetCDFSource` | Suppression de `Data` |
| `self._dataset` | `self._ds` | Abréviation standard xarray (`ds`) |
| `self._last_data_array` | `self._da` | Abréviation standard xarray (`da`) |
| `self.file_path` | `self.path` | Cohérence |
| `self.use_dask` | inchangé | Clair |
| `_charger_dataset()` | `_open()` | Simple et expressif |
| `get_dimensions()` | `dims()` | Analogie xarray `ds.dims` |
| `to_dataframe()` | `to_df()` | Abréviation courante |

### `APIDataSource`

| Elément actuel | Proposition | Raison |
|---|---|---|
| `APIDataSource` (classe) | `APISource` | Suppression de `Data` |
| `self._last_request_time` | `self._last_req` | Plus court |
| `self._schema_cache` | `self._schema` | Plus simple |
| `self.api_url` | `self.url` | Sans redondance (`APISource.url`, c'est déjà une URL d'API) |
| `self.auth_token` | `self.token` | Plus court |
| `self.rate_limit_per_sec` | `self.rate_limit` | L'unité est implicite (sec standard) |
| `_construire_entetes()` | `_build_headers()` | En anglais, cohérent |
| `_respecter_rate_limit()` | `_throttle()` | Terme technique consacré |
| `fetch_with_retry(params, max_retries, backoff_sec)` | `fetch(params, retries, backoff)` | Retrait de `with_retry` (comportement intégré) |

---

## 4. Pipeline KIDAS — `kadi.kidas`

### `DataCleaner`

| Elément actuel | Proposition | Raison |
|---|---|---|
| `DataCleaner` (classe) | `Cleaner` | Préfixe `Data` redondant |
| `self._rapport` | `self._report` | En anglais, cohérent avec le reste du code |
| `self.df` | inchangé | Standard universel |
| `remove_duplicates(subset, keep)` | `drop_dupes(subset, keep)` | `drop_` préfixe Pandas (`drop_duplicates`) |
| `handle_missing_values(strategy, columns)` | `fill_missing(strategy, cols)` | Plus court et expressif |
| `remove_outliers(method, threshold, columns)` | `drop_outliers(method, thresh, cols)` | Cohérence `drop_` + abréviations |
| `fix_dates(columns, infer_format)` | `parse_dates(cols, infer)` | Analogie Pandas `parse_dates=` |
| `standardize_text(columns, case)` | `norm_text(cols, case)` | `norm_` préfixe cohérent |
| `remove_special_chars(columns, keep_chars)` | `strip_chars(cols, keep)` | Plus court |
| `detect_inconsistent_decimals(columns)` | `check_decimals(cols)` | `check_` clair et neutre |
| `get_cleaning_report()` | `report()` | Cohérence avec `info()` |

### `DataValidator`

| Elément actuel | Proposition | Raison |
|---|---|---|
| `DataValidator` (classe) | `Validator` | Préfixe `Data` redondant |
| `self._rapport` | `self._report` | En anglais |
| `validate_schema(schema)` | `check_schema(schema)` | `check_` plus court que `validate_` |
| `validate_types(column_dtypes)` | `check_types(dtypes)` | Idem, paramètre abrégé |
| `validate_ranges(column_bounds)` | `check_ranges(bounds)` | Idem |
| `validate_coordinates(lat_col, lon_col, region)` | `check_coords(lat, lon, region)` | Abréviation naturelle |
| `validate_uniqueness(columns)` | `check_unique(cols)` | Plus court |
| `validate_referential_integrity(fk_col, reference_set)` | `check_fk(fk_col, ref)` | `fk` = clé étrangère, terme clair |
| `compute_quality_score()` | `quality_score()` | Suppression de `compute_`, résultat direct |
| `get_validation_report()` | `report()` | Cohérence |

### `DataNormalizer`

| Elément actuel | Proposition | Raison |
|---|---|---|
| `DataNormalizer` (classe) | `Normalizer` | Préfixe `Data` redondant |
| `self._mappings` | inchangé | Clair |
| `_vers_snake_case(texte)` | `_to_snake(text)` | En anglais, plus court |
| `normalize_column_names(style)` | `norm_cols(style)` | Plus direct |
| `normalize_units(unit_map)` | `convert_units(unit_map)` | `convert_` plus précis |
| `normalize_currencies(col, from_currency, to_currency, exchange_date)` | `convert_currency(col, from, to, date)` | Singulier, paramètres courts |
| `normalize_crop_names(col, target_standard)` | `std_crops(col, std)` | `std_` préfixe pour standardisation |
| `normalize_market_names(col, region)` | `std_markets(col, region)` | Idem |
| `normalize_geometry(lat_col, lon_col)` | `std_coords(lat, lon)` | Idem |
| `get_normalization_mapping()` | `mappings()` | Direct, sans verbe |

### `DataCache`

| Elément actuel | Proposition | Raison |
|---|---|---|
| `DataCache` (classe) | `Cache` | Préfixe `Data` redondant |
| `self.cache_dir` | `self.dir` | Plus court dans ce contexte |
| `self.db_path` | `self.db` | Plus court |
| `self.max_age_days` | `self.ttl` | `ttl` = Time-To-Live, terme standard |
| `_creer_repertoire()` | `_mkdir()` | Terme UNIX consacré |
| `_obtenir_connexion()` | `_connect()` | Standard |
| `_initialiser_db()` | `_init_db()` | Abréviation standard |
| `_serialiser(data)` | `_pack(data)` | Court et expressif |
| `_deserialiser(blob)` | `_unpack(blob)` | Symétrique |
| `save(key, data, metadata)` | `set(key, data, meta)` | Analogie dict/Redis |
| `load(key, check_validity)` | `get(key, check)` | Analogie dict/Redis |
| `get_cached_keys()` | `keys()` | Analogie dict |
| `invalidate(key)` | `delete(key)` | Terme standard |
| `invalidate_older_than(days)` | `purge(days)` | Court et précis |
| `get_cache_size()` | `size()` | Direct |
| `clear()` | inchangé | Déjà parfait (analogie dict) |
| `get_history(key)` | `history(key)` | Sans `get_` |

### `DataPipeline`

| Elément actuel | Proposition | Raison |
|---|---|---|
| `DataPipeline` (classe) | `Pipeline` | Préfixe `Data` redondant |
| `self._cache` | inchangé | Clair |
| `self._df` | inchangé | Standard |
| `self._etapes` | `self._steps` | En anglais |
| `self._lignes_avant` | `self._nrows_in` | En anglais, plus précis |
| `self._rapports` | `self._reports` | En anglais |
| `self._source` | inchangé | Clair |
| `_detecter_type_source(source)` | `_detect_kind(source)` | En anglais, `kind` cohérent |
| `load_data(source)` | `load(source)` | `_data` redondant |
| `add_cleaning_step(step_name)` | `clean(step)` | Verbe direct, sans `add_` |
| `add_validation_step(schema)` | `validate(schema)` | Idem |
| `add_normalization_step(mappings)` | `normalize(mappings)` | Idem |
| `execute(cache)` | `run(cache)` | Terme universel |
| `_extraire_warnings()` | `_collect_warnings()` | En anglais |
| `_executer_etape(etape)` | `_run_step(step)` | En anglais |
| `get_pipeline_config()` | `config()` | Sans `get_` |
| `export_report(filepath)` | `export(path)` | Plus court |

---

## 5. Module market — `kadi.market`

### `Market` (façade)

| Elément actuel | Proposition | Raison |
|---|---|---|
| `Market` (classe) | inchangé | Déjà court et clair |
| `self.decision_support` | `self.advisor` | Plus court et expressif |
| `self.forecasting` | `self.forecast` | Nom du module, pas de la fonction |
| `self.lat` | inchangé | Standard géographique |
| `self.location` | inchangé | Clair |
| `self.logistics` | inchangé | Clair |
| `self.lon` | inchangé | Standard géographique |
| `self.pricing` | inchangé | Clair |
| `self.simulated` | `self.sim` | Plus court |
| `self.weather_session` | `self.weather` | Plus court |
| `price_crop(crop, days_back, normalize_to_xof_kg, simulated)` | `price(crop, days, normalize, sim)` | Sans `_crop`, paramètres courts |
| `predict_price(crop, days_ahead, confidence_interval, days_back, simulated)` | `predict(crop, ahead, ci, days, sim)` | `ci` = confidence interval, standard |
| `seasonality(crop, days_back, simulated)` | `seasonality(crop, days, sim)` | `sim` = Plus court |
| `assess_climate_risk(days_ahead)` | `climate_risk(ahead)` | Sans `assess_`, plus direct |

### `MarketPricing`

| Elément actuel | Proposition | Raison |
|---|---|---|
| `MarketPricing` (classe) | `Pricing` | Préfixe `Market` redondant dans `kadi.market` |
| `self._exchange_rates` | `self._fx` | `fx` = foreign exchange, abréviation standard |
| `self.simulated` | `self.sim` | Plus court |
| `self.wfp_client` | `self.client` | Sans redondance dans ce contexte |
| `fetch_prices(crop, market, days_back, simulated)` | `fetch(crop, market, days, sim)` | Sans `_prices`, paramètres courts |
| `_generer_donnees_simulees(...)` | `_simulate(...)` | En anglais, plus court |
| `normalize_units(value, unit_orig, crop)` | `convert_unit(value, unit, crop)` | `convert_` plus précis, singulier |
| `detect_anomalies(price_series, z_threshold)` | `anomalies(series, z)` | Sans `detect_`, résultat direct |
| `interpolate_gaps(price_series, max_gap_days)` | `fill_gaps(series, max_gap)` | `fill_` plus intuitif |
| `get_data_source(price_series)` | `source(series)` | Sans `get_data_` |
| `seasonality(historique, min_observations_par_mois)` | `seasonality(hist, min_obs)` | Paramètres abrégés |

### `MarketForecasting`

| Elément actuel | Proposition | Raison |
|---|---|---|
| `MarketForecasting` (classe) | `Forecasting` | Préfixe `Market` redondant |
| `self._modele` | `self._model` | En anglais |
| `_preparer_features(prix_series)` | `_build_features(series)` | En anglais |
| `_calculer_rmse_cv(X, y)` | `_cv_rmse(X, y)` | Ordre logique : méthode d'abord |
| `_construire_df_propre(historique)` | `_clean_df(hist)` | En anglais, plus court |
| `_fallback_simule(days_ahead, confidence_interval)` | `_fallback(ahead, ci)` | Paramètres courts |
| `predict_price(crop, market, days_ahead, confidence_interval, historique)` | `predict(crop, market, ahead, ci, hist)` | Sans `_price`, paramètres courts |

### `MarketLogistics`

| Elément actuel | Proposition | Raison |
|---|---|---|
| `MarketLogistics` (classe) | `Logistics` | Préfixe `Market` redondant |
| `self._cached_fuel_price` | `self._fuel` | Plus court |
| `self._cached_prob_pluie` | `self._rain_prob` | En anglais |
| `self.cache` | inchangé | Clair |
| `self.cache_file` | inchangé | Clair |
| `self.weather_session` | `self.weather` | Plus court |
| `_get_prob_pluie()` | `_rain_prob()` | En anglais, cohérent avec l'attribut |
| `_haversine_distance(lon1, lat1, lon2, lat2)` | `_haversine(lon1, lat1, lon2, lat2)` | Sans `_distance`, déjà implicite |
| `_geocode_city(city_name)` | `_geocode(city)` | Sans `_city`, paramètre raccourci |
| `_fetch_osrm_distance(lon1, lat1, lon2, lat2)` | `_osrm_dist(lon1, lat1, lon2, lat2)` | Plus court |
| `get_distance(origine, destination)` | `distance(origin, dest)` | Sans `get_`, `origin` anglais standard |
| `_fetch_fuel_price()` | `_fetch_fuel()` | Plus court |
| `calculate_transfer_cost(origine, destination, prix_carburant, crop)` | `transfer_cost(origin, dest, fuel_price, crop)` | En anglais, sans `calculate_` |

### `DecisionSupport`

| Elément actuel | Proposition | Raison |
|---|---|---|
| `DecisionSupport` (classe) | `Advisor` | Plus court, plus expressif |
| `self.forecasting` | `self.forecast` | Nom raccourci |
| `self.logistics` | inchangé | Clair |
| `self.pricing` | inchangé | Clair |
| `__init__(forecasting_module, logistics_module, pricing_module)` | `__init__(forecast, logistics, pricing)` | Sans `_module` |
| `_obtenir_prix_marche(crop, market)` | `_get_price(crop, market)` | En anglais |
| `_calculer_confidence_score(...)` | `_confidence(...)` | Plus court, sans `_calculer_score` |
| `arbitrage_decision(crop, market_from, market_to, qty_tons)` | `arbitrage(crop, from_, to, qty)` | Sans `_decision`, `from_` évite le mot-clé Python |
| `storage_vs_sell_now(crop, market, current_price, qty_tons, mois_stockage)` | `store_or_sell(crop, market, price, qty, months)` | Plus clair, paramètres en anglais |
| `portfolio_optimization(available_land_ha, climate_forecast, market_forecast, rendements_t_ha)` | `optimize(land_ha, climate, market, yields)` | Beaucoup plus court |
| `_portfolio_heuristique(available_land_ha, climate_forecast, market_forecast)` | `_heuristic(land_ha, climate, market)` | En anglais, sans `_portfolio` |

### `MarketBacktester`

| Elément actuel | Proposition | Raison |
|---|---|---|
| `MarketBacktester` (classe) | `Backtester` | Préfixe `Market` redondant |
| `self._forecaster` | inchangé | Clair |
| `self._resultats` | `self._results` | En anglais |
| `_calculer_mae(y_reel, y_pred)` | `_mae(y_true, y_pred)` | `y_true` est le standard scikit-learn |
| `_calculer_rmse(y_reel, y_pred)` | `_rmse(y_true, y_pred)` | Idem |
| `_calculer_mape(y_reel, y_pred)` | `_mape(y_true, y_pred)` | Idem |
| `_calculer_precision_directionnelle(y_reel, y_pred)` | `_dir_acc(y_true, y_pred)` | `dir_acc` = directional accuracy |
| `run(crop, market, historique, window_days, horizon_days, nb_fenetres)` | `run(crop, market, hist, window, horizon, n)` | Paramètres courts |
| `summary_report()` | `summary()` | Sans `_report`, cohérent avec `report()` |

### `WFPDataBridgesClient` (dans `market.data_ingestion`)

> A fusionner avec `kadi._sources.wfp_client`. En attendant, propositions :

| Elément actuel | Proposition | Raison |
|---|---|---|
| `WFPDataBridgesClient` (classe) | `WFPClient` | Suppression de `DataBridges`, plus court |
| `self.base_url` | `self.url` | Cohérence avec les autres clients |
| `self.retry_attempts` | `self.retries` | Plus court |
| `self.retry_backoff_sec` | `self.backoff` | Plus court |
| `self.use_local_mirror` | `self.mirror` | Plus court |
| `_charger_cache_ids()` | `_load_ids()` | En anglais |
| `_sauvegarder_cache_ids()` | `_save_ids()` | En anglais |
| `_charger_token(env_file)` | `_load_token(env_file)` | En anglais |
| `_recuperer_commodites()` | `_fetch_commodities()` | En anglais |
| `_recuperer_marches(country_code)` | `_fetch_markets(country)` | En anglais, paramètre court |
| `_get_commodity_id(commodity_name)` | `_commodity_id(name)` | Sans `_get_`, paramètre court |
| `_get_market_id(market_name)` | `_market_id(name)` | Idem |
| `_validate_api_response_items(items)` | `_check_items(items)` | Plus court |
| `get_market_prices(market_name, commodity, time_range)` | `prices(market, commodity, range_)` | Sans `get_market_`, `range_` évite le builtin |
| `get_market_functionality_index(market_id)` | `mfi(market_id)` | `mfi` = Market Functionality Index, acronyme standard WFP |
| `_generer_donnees_simulees(time_range)` | `_simulate(range_)` | Cohérence |

---

## 6. Module weather — `kadi.weather`

### `Location`

| Elément actuel | Proposition | Raison |
|---|---|---|
| `Location` (classe) | inchangé | Déjà court et universel |
| `self.climate_regime` | `self.regime` | `climate_` redondant dans ce contexte |
| `self.latitude` | `self.lat` | Abréviation standard géo (Pandas GeoDataFrame) |
| `self.longitude` | `self.lon` | Idem |
| `self.name` | inchangé | Parfait |
| `self.zone` | inchangé | Clair |
| `detect_zone()` | `zone()` | Résultat direct, sans `detect_` |
| `_detect_regime()` | `_regime()` | Idem, interne |
| `get_climate_params()` | `climate()` | Sans `get_` et `_params` |
| `to_dict()` | inchangé | Standard Python |

### `WeatherData`

| Elément actuel | Proposition | Raison |
|---|---|---|
| `WeatherData` (classe) | `WeatherLoader` | `Data` trop générique, `Loader` décrit le rôle |
| `self.data_source` | `self.source` | Sans `data_` |
| `self.forecast_data` | `self.forecast` | Sans `_data` |
| `self.historical_data` | `self.historical` | Sans `_data` |
| `self.location` | inchangé | Clair |
| `_unifier_colonne_temperature(df)` | `_unify_temp(df)` | En anglais, plus court |
| `fetch_forecast(days, force_refresh)` | `get_forecast(days, refresh)` | Paramètre court |
| `fetch_historical(months_back, force_refresh, source)` | `get_historical(months, refresh, source)` | `months` plus court |
| `_get_from_cache(start_date, end_date)` | `_from_cache(start, end)` | Sans `_get_`, paramètres courts |
| `_save_to_cache(data, data_type)` | `_to_cache(data, kind)` | Symétrique, `kind` cohérent |
| `_fetch_forecast_data(days)` | `_fetch_forecast(days)` | Sans `_data` |
| `_fetch_historical_data(days, source)` | `_fetch_historical(days, source)` | Sans `_data` |
| `_normalize_data(raw_data)` | `_normalize(raw)` | Sans `_data`, paramètre court |

### `Hydrology`

| Elément actuel | Proposition | Raison |
|---|---|---|
| `Hydrology` (classe) | inchangé | Terme scientifique précis, déjà bon |
| `self.balance_result` | `self.balance` | Sans `_result` |
| `self.crop` | inchangé | Clair |
| `self.location` | inchangé | Clair |
| `self.rainfall_data` | `self.rainfall` | Sans `_data` |
| `self.soil_params` | `self.soil` | Sans `_params` |
| `self.soil_type` | inchangé | Clair |
| `self.temperature_data` | `self.temperature` | Sans `_data` |
| `_resolve_soil_type_from_cache(location)` | `_resolve_soil(location)` | Plus court |
| `et0_hargreaves(tmin, tmax, day_of_year)` | inchangé | Nom scientifique officiel, à conserver |
| `et0_fao56_penman(tmin, tmax, humidity, wind_speed, solar_rad)` | inchangé | Idem |
| `runoff_cn(precipitation, prior_5d_rain)` | inchangé | Terme agronomique standard |
| `compute_water_balance()` | `water_balance()` | Sans `compute_` |
| `get_soil_params(soil_type)` | `soil_params(soil_type)` | Sans `get_` |
| `get_crop_coefficients(crop, stage)` | `crop_kc(crop, stage)` | `kc` = crop coefficient, terme FAO standard |

### `Phenology`

| Elément actuel | Proposition | Raison |
|---|---|---|
| `Phenology` (classe) | inchangé | Terme scientifique précis |
| `self.crop_params` | `self.crop` | Plus court |
| `self.location` | inchangé | Clair |
| `self.onset_date` | `self.onset` | Sans `_date`, le type est évident |
| `self.rainfall_data` | `self.rainfall` | Sans `_data` |
| `self.temperature_data` | `self.temperature` | Sans `_data` |
| `onset(threshold_days_after)` | `onset(threshold)` | Plus court |
| `cessation()` | inchangé | Terme agronomique standard |
| `growing_degree_days(crop, start_date, end_date)` | `gdd(crop, start, end)` | `gdd` = Growing Degree Days, acronyme consacré |
| `_sivakumar(...)` | inchangé | Nom de l'auteur de la méthode, à conserver |
| `_walter_anyadike(year, annual_precipitation)` | inchangé | Idem |
| `_walter_anyadike_bimodal(year, season)` | inchangé | Idem |
| `_cessation_in_window(...)` | inchangé | Suffisamment clair |

### `RiskIndicators`

| Elément actuel | Proposition | Raison |
|---|---|---|
| `RiskIndicators` (classe) | `Risk` | Plus court, sans `Indicators` |
| `self.forecast_data` | `self.forecast` | Sans `_data` |
| `self.location` | inchangé | Clair |
| `self.rainfall_historical` | `self.rainfall` | Plus court |
| `drought_index(method, window_months)` | `drought(method, window)` | Sans `_index`, plus court |
| `spi(window_months)` | `spi(window)` | Paramètre raccourci |
| `markov_transition(threshold_mm)` | `markov(thresh)` | Plus court |
| `hurst_exponent(window)` | `hurst(window)` | Sans `_exponent` |
| `rain_probability(days_ahead, min_rainfall_mm)` | `rain_prob(days, min_mm)` | Plus court |
| `_get_severity_level(spi_value)` | `_severity(spi)` | Sans `get_` et `_level` |

### `WeatherSession` (façade)

| Elément actuel | Proposition | Raison |
|---|---|---|
| `WeatherSession` (classe) | `Weather` | Façade principale : nom simple comme `Market` |
| `self.cache_dir` | `self.cache` | Plus court |
| `self.hydrology` | inchangé | Clair |
| `self.location` | inchangé | Clair |
| `self.phenology` | inchangé | Clair |
| `self.risk_indicators` | `self.risk` | Cohérence avec la classe `Risk` |
| `self.weather_data` | `self.loader` | Cohérence avec `WeatherLoader` |
| `__init__(latitude, longitude, name, cache_dir)` | `__init__(lat, lon, name, cache)` | Paramètres courts |
| `_ensure_data(require_forecast, require_historical)` | `_load_data(forecast, historical)` | Plus direct |
| `_ensure_components(component)` | `_init_component(component)` | Plus précis |
| `forecast(days)` | inchangé | Déjà parfait |
| `historical(metric, months_back, source)` | `historical(metric, months, source)` | `months` plus court |
| `growing_degree_days(crop, start_date, end_date)` | `gdd(crop, start, end)` | Cohérence avec `Phenology` |
| `onset()` | inchangé | Standard agronomique |
| `cessation()` | inchangé | Standard agronomique |
| `drought_index(method, window_months)` | `drought(method, window)` | Cohérence avec `Risk` |
| `rain_probability(days_ahead, min_rainfall_mm)` | `rain_prob(days, min_mm)` | Cohérence avec `Risk` |
| `water_balance(crop, soil_type)` | inchangé | Terme agronomique standard |
| `et0_hargreaves(tmin, tmax, day_of_year)` | inchangé | Terme scientifique standard |
| `_init_all_components()` | `_setup()` | Plus court et universel |

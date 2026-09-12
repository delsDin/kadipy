# Normalizer (`kadi.kidas.normalizer`)

`Normalizer` est la classe de normalisation des données agricoles de KadiPy,
orientée vers le contexte béninois. Elle regroupe six transformations :
normalisation des noms de colonnes en snake_case, conversion d'unités de
mesure vers le kilogramme, conversion de devises, standardisation des noms
de cultures vers les codes FAO, géocodage des noms de marchés, et création
de géométries GPS shapely.

Chaque méthode met à jour le DataFrame interne et le retourne, ce qui permet
d'enchaîner les appels en une seule expression. L'historique des transformations
appliquées est accessible via `mappings()`.

---

## Initialisation

```python
from kadi.kidas import Normalizer

normalizer = Normalizer(df)
```

`Normalizer` reçoit un `pandas.DataFrame` et en crée une copie interne. Le
DataFrame original n'est jamais modifié.

**Exception :** `CleanError` si l'argument fourni n'est pas un DataFrame.

---

## Méthodes de normalisation

### `norm_cols(style='snake_case')`

Normalise les noms de colonnes du DataFrame en snake_case : suppression des
accents, remplacement des espaces, tirets et parenthèses par des underscores,
conversion en minuscules.

```python
# Avant : ['Culture', 'Rendement (kg)', 'Température Min (°C)', 'Date Récolte']
df_norm = normalizer.norm_cols()
# Après : ['culture', 'rendement_kg', 'temperature_min_c', 'date_recolte']
```

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `style` | `str` | `'snake_case'` | Style cible. Seul `'snake_case'` est supporté actuellement. |

Un style différent de `'snake_case'` génère un avertissement dans les logs
et l'opération est quand même appliquée en snake_case.

**Retour :** `pd.DataFrame`

---

### `convert_units(unit_map)`

Convertit les valeurs numériques des colonnes spécifiées vers le kilogramme,
en appliquant les facteurs de conversion du référentiel interne.

```python
df_norm = normalizer.convert_units({
    "production":  "tonne",
    "recolte":     "sac_100kg",
    "stock_local": "tiya",
})
```

| Paramètre | Type | Description |
|-----------|------|-------------|
| `unit_map` | `dict[str, str]` | Dictionnaire `nom_colonne` → `unité source` |

**Unités supportées :**

| Unité | Facteur vers kg |
|-------|-----------------|
| `'kg'`, `'kilogramme'` | 1.0 |
| `'tonne'`, `'tonnes'`, `'t'` | 1000.0 |
| `'sac_100kg'`, `'sac'` | 100.0 |
| `'sac_80kg'` | 80.0 |
| `'sac_50kg'` | 50.0 |
| `'tiya'` | 1.5 |
| `'quintal'` | 100.0 |
| `'boisseau'` | 27.2 |
| `'livre'` | 0.4536 |
| `'g'`, `'gramme'` | 0.001 |

Le `'sac'` standard correspond au sac de 100 kg utilisé au Bénin. Le `'tiya'`
est une mesure locale d'environ 1.5 kg selon la culture. Une colonne absente
du DataFrame génère un avertissement dans les logs et est ignorée sans erreur.

**Retour :** `pd.DataFrame`

**Exception :** `CleanError` si une unité source est inconnue.

---

### `convert_currency(col, from_='XOF', to='XOF', date=None)`

Convertit les valeurs monétaires d'une colonne selon un taux de change fixe.

```python
# Conversion de USD vers XOF
df_norm = normalizer.convert_currency(
    col="prix_usd",
    from_="USD",
    to="XOF",
)

# Conversion d'EUR vers XOF
df_norm = normalizer.convert_currency(
    col="valeur_export",
    from_="EUR",
    to="XOF",
)
```

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `col` | `str` | - | Nom de la colonne à convertir |
| `from_` | `str` | `'XOF'` | Devise source |
| `to` | `str` | `'XOF'` | Devise cible |
| `date` | `str` ou `None` | `None` | Date de référence au format `'YYYY-MM-DD'` (non utilisée dans la version actuelle) |

**Taux de change disponibles (fixes, vers XOF) :**

| Devise | Taux vers XOF |
|--------|---------------|
| `'XOF'` | 1.0 |
| `'EUR'` | 655.957 (taux fixe UMOA) |
| `'USD'` | 600.0 |
| `'GBP'` | 750.0 |

Si l'une des devises n'est pas dans ce tableau, un avertissement est émis et
aucune conversion n'est appliquée.

> La version actuelle utilise des taux fixes. L'intégration avec une API de
> change en temps réel est prévue en phase 2 du module.

**Retour :** `pd.DataFrame`

---

### `std_crops(col, std='fao')`

Normalise les noms de cultures d'une colonne vers les codes FAO officiels, en
gérant les variantes locales béninoises avec ou sans accents.

```python
# Avant : ['maïs', 'Niébé', 'MANIOC', 'yam', 'mais']
df_norm = normalizer.std_crops(col="culture")
# Après : ['maize', 'cowpea', 'cassava', 'yam', 'maize']
```

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `col` | `str` | - | Nom de la colonne contenant les noms de cultures |
| `std` | `str` | `'fao'` | Standard cible (`'fao'` utilise les codes officiels FAO) |

**Correspondances disponibles :**

| Noms locaux acceptés | Code FAO |
|----------------------|----------|
| `'maïs'`, `'mais'`, `'maiz'`, `'corn'`, `'maize'` | `'maize'` |
| `'niébé'`, `'niebe'`, `'cowpea'`, `'haricot'` | `'cowpea'` |
| `'igname'`, `'yam'` | `'yam'` |
| `'sorgho'`, `'sorghum'` | `'sorghum'` |
| `'riz'`, `'rice'` | `'rice'` |
| `'manioc'`, `'cassava'` | `'cassava'` |
| `'arachide'`, `'groundnut'`, `'peanut'` | `'groundnut'` |
| `'mil'`, `'millet'` | `'millet'` |
| `'fonio'` | `'fonio'` |
| `'soja'`, `'soybean'` | `'soybean'` |
| `'tomate'`, `'tomato'` | `'tomato'` |
| `'oignon'`, `'onion'` | `'onion'` |
| `'piment'`, `'pepper'` | `'pepper'` |

Les noms non reconnus sont conservés en minuscules sans accents. Une colonne
absente génère un avertissement et est ignorée.

**Retour :** `pd.DataFrame`

---

### `std_markets(col, region='benin')`

Normalise les noms de marchés d'une colonne et ajoute deux colonnes
`market_lat` et `market_lon` avec les coordonnées GPS officielles.

```python
# Avant : ['Dantokpa', 'PARAKOU', 'Bohicon']
df_norm = normalizer.std_markets(col="marche")
# Après : colonne 'marche' inchangée, + colonnes 'market_lat' et 'market_lon'
```

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `col` | `str` | - | Nom de la colonne contenant les noms de marchés |
| `region` | `str` | `'benin'` | Région de référence pour le dictionnaire de marchés |

**Marchés référencés (Bénin) :**

| Marché | Latitude | Longitude | Ville |
|--------|----------|-----------|-------|
| `dantokpa`, `cotonou` | 6.366 | 2.437 | Cotonou |
| `parakou` | 9.337 | 2.629 | Parakou |
| `bohicon` | 7.181 | 2.067 | Bohicon |
| `kandi` | 11.133 | 2.940 | Kandi |
| `natitingou` | 10.303 | 1.381 | Natitingou |
| `malanville` | 11.867 | 3.383 | Malanville |
| `abomey` | 7.183 | 1.983 | Abomey |
| `porto-novo` | 6.497 | 2.627 | Porto-Novo |
| `lokossa` | 6.617 | 1.717 | Lokossa |

La correspondance est partielle : `'Marché de Parakou'` sera associé à
`'parakou'`. Les marchés non reconnus reçoivent `None` pour lat et lon.
Une colonne absente génère un avertissement et est ignorée.

**Retour :** `pd.DataFrame` avec les colonnes `market_lat` et `market_lon`
ajoutées.

---

### `std_coords(lat=None, lon=None)`

Crée une colonne `geometry` contenant des objets `shapely.geometry.Point`
à partir des colonnes de latitude et longitude.

```python
df_norm = normalizer.std_coords(lat="latitude", lon="longitude")
# Colonne 'geometry' ajoutée : Point(lon, lat) pour chaque ligne
```

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `lat` | `str` ou `None` | `None` | Nom de la colonne de latitude |
| `lon` | `str` ou `None` | `None` | Nom de la colonne de longitude |

Si `lat` ou `lon` est `None` ou désigne une colonne absente du DataFrame,
un avertissement est émis dans les logs et le DataFrame est retourné sans
modification.

Les lignes dont la latitude ou la longitude est `NaN` reçoivent `None`
dans la colonne `geometry`.

Si le package `shapely` n'est pas installé, un avertissement est émis et
le DataFrame est retourné sans modification.

> Dépendance optionnelle : `shapely >= 2.0`. Installez-la avec
> `pip install shapely>=2.0`.

**Retour :** `pd.DataFrame` avec la colonne `geometry` ajoutée.

---

### `mappings()`

Retourne l'historique complet des normalisations appliquées depuis
l'initialisation du `Normalizer`.

```python
normalizer.norm_cols()
normalizer.std_crops(col="culture")
normalizer.convert_units({"production": "tonne"})

hist = normalizer.mappings()
# {
#   "colonnes": {"Rendement (kg)": "rendement_kg", ...},
#   "unites":   {"production": {"unite_source": "tonne", "facteur_kg": 1000.0, "unite_cible": "kg"}},
#   "cultures": {"maïs": "maize", "Niébé": "cowpea"},
#   "marches":  {},
#   "devises":  {},
# }
```

| Clé | Type | Contenu |
|-----|------|---------|
| `colonnes` | `dict` | `ancien_nom` → `nouveau_nom` pour chaque colonne renommée |
| `unites` | `dict` | `colonne` → `{unite_source, facteur_kg, unite_cible}` |
| `cultures` | `dict` | `nom_local` → `code_fao` pour chaque correspondance trouvée |
| `marches` | `dict` | Vide dans la version actuelle |
| `devises` | `dict` | `colonne` → `{from, to, taux}` |

**Retour :** `dict` (copie de l'historique interne).

---

## Exemple complet enchaîné

```python
import kadi as kd
from kadi.kidas import Normalizer

df = kd.read_csv("recoltes_2024.csv")
normalizer = Normalizer(df)

df_norm = (
    normalizer
    .norm_cols()
    .std_crops(col="culture")
    .convert_units({"rendement_kg": "sac_100kg", "production": "tonne"})
    .std_markets(col="marche")
    .std_coords(lat="latitude", lon="longitude")
)

hist = normalizer.mappings()
print(f"Colonnes renommées : {len(hist['colonnes'])}")
print(f"Cultures normalisées : {len(hist['cultures'])}")
print(f"Unités converties : {len(hist['unites'])}")
```

---

## Utilisation dans un Pipeline

`Normalizer` est utilisé en interne par `Pipeline` lorsqu'on ajoute une étape
de normalisation via `add_step` ou `normalize`.

```python
from kadi.kidas import Pipeline

df, rapport = (
    Pipeline()
    .add_source("recoltes_2024.csv")
    .add_step("norm_cols")
    .add_step("std_crops", col="culture")
    .add_step("convert_units", unit_map={"rendement_kg": "sac_100kg"})
    .run()
)
```

Pour la documentation du pipeline, voir [Pipeline](pipeline.md).

---

## Rétrocompatibilité

Les anciens noms de méthodes émettent un `DeprecationWarning` et continuent
de fonctionner jusqu'à KadiPy v2.0 :

| Ancien nom (avant v1.2.0) | Nouveau nom |
|---------------------------|-------------|
| `normalize_column_names()` | `norm_cols()` |
| `normalize_units()` | `convert_units()` |
| `normalize_currencies()` | `convert_currency()` |
| `normalize_crop_names()` | `std_crops()` |
| `normalize_market_names()` | `std_markets()` |
| `normalize_geometry()` | `std_coords()` |
| `get_normalization_mapping()` | `mappings()` |

De même, le nom de classe `DataNormalizer` est un alias de `Normalizer`.

---

::: kadi.kidas.normalizer.Normalizer

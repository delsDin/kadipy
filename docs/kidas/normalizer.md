# Normalisation (`kadi.kidas.normalizer`)

`DataNormalizer` standardise les données vers les référentiels internes de
KadiPy : noms de cultures, noms de marchés, coordonnées GPS, et unités de
mesure.

---

## Initialisation

```python
from kadi.kidas import DataNormalizer
import pandas as pd

df = pd.read_csv("recoltes_2024.csv")
normalizer = DataNormalizer(df)
```

---

## Méthodes

### `normalize_crops(column)`

Traduit les noms locaux de cultures vers les codes standardisés KadiPy.

```python
df = normalizer.normalize_crops(column="culture")
```

**Exemples de correspondances :**

| Nom local (français/fon/dendi) | Code KadiPy |
|-------------------------------|-------------|
| `"maïs"`, `"maize"`, `"baba"` | `"maize"` |
| `"riz"`, `"rice"`, `"maro"` | `"rice"` |
| `"igname"`, `"yam"`, `"isu"` | `"yam"` |
| `"manioc"`, `"cassava"` | `"cassava"` |
| `"niébé"`, `"cowpea"`, `"ewa"` | `"cowpea"` |
| `"sorgho"`, `"sorghum"`, `"dawa"` | `"sorghum"` |
| `"mil"`, `"millet"` | `"millet"` |
| `"tomate"`, `"tomato"` | `"tomato"` |
| `"oignon"`, `"onion"` | `"onion"` |
| `"soja"`, `"soybean"` | `"soybean"` |

---

### `normalize_markets(column)`

Traduit les noms de marchés vers les identifiants officiels WFP / OSM.

```python
df = normalizer.normalize_markets(column="marche")
```

**Exemples :**

| Nom local | Identifiant normalisé |
|-----------|----------------------|
| `"Dantokpa"`, `"dantokpa"` | `"cotonou"` |
| `"Savalou"`, `"Savalou_Market"` | `"savalou"` |
| `"PK5"`, `"pk5"` | `"parakou"` |

---

### `normalize_gps(lat_col, lon_col)`

Valide et corrige les coordonnées GPS pour s'assurer qu'elles sont dans les
bornes du Bénin.

```python
df = normalizer.normalize_gps(lat_col="latitude", lon_col="longitude")
```

**Règles appliquées :**

| Vérification | Borne min | Borne max |
|-------------|-----------|-----------|
| Latitude | 6.0° N | 12.5° N |
| Longitude | 0.5° E | 3.9° E |

Les coordonnées hors bornes sont marquées `NaN` et signalées dans le rapport.

---

### `normalize_units(value_col, unit_col, target_unit)`

Convertit les quantités vers une unité cible.

```python
# Convertir toutes les quantités en kg
df = normalizer.normalize_units(
    value_col="quantite",
    unit_col="unite",
    target_unit="kg",
)

# Convertir les prix vers XOF/kg
df = normalizer.normalize_units(
    value_col="prix",
    unit_col="unite_prix",
    target_unit="xof_kg",
)
```

**Conversions supportées vers kg :**

| Unité d'entrée | Facteur | Résultat |
|---------------|---------|---------|
| `"g"` / `"gramme"` | × 0.001 | kg |
| `"kg"` | × 1 | kg (inchangé) |
| `"t"` / `"tonne"` | × 1 000 | kg |
| `"sac50"` | × 50 | kg |
| `"sac100"` | × 100 | kg |
| `"muids"` | × 200 | kg |

---

## Exemple complet

```python
import pandas as pd
from kadi.kidas import DataNormalizer

df = pd.read_csv("enquete_agriculteurs_locale.csv")

normalizer = DataNormalizer(df)

df_standardise = (
    normalizer
    .normalize_crops(column="culture")
    .normalize_markets(column="commune_marche")
    .normalize_gps(lat_col="latitude", lon_col="longitude")
    .normalize_units(value_col="rendement", unit_col="unite", target_unit="kg")
)

# Vérification
print(df_standardise["culture"].unique())
# ['maize', 'rice', 'yam', 'cassava']  -- codes KadiPy uniformes

print(df_standardise[["latitude", "longitude"]].describe())
# Vérifier que toutes les coordonnées sont dans les bornes du Bénin
```

---

## Utilisation dans un pipeline

```python
from kadi.kidas import DataPipeline

pipeline = DataPipeline()

df, rapport = (
    pipeline
    .load_data("enquete_2024.csv")
    .add_cleaning_step("remove_duplicates")
    .add_normalization_step({
        "crops": "culture",
        "markets": "marche",
        "gps": ["latitude", "longitude"],
    })
    .execute(cache=True)
)
```

---

::: kadi.kidas.normalizer.DataNormalizer

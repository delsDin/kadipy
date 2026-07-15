# Risques climatiques (`kadi.weather.risk`)

Le module `RiskIndicators` analyse les données météo pour produire des alertes
opérationnelles : probabilité de pluie imminente et indices de sécheresse
multi-méthodes.

---

## Probabilité de pluie

La probabilité de pluie combine deux sources complémentaires :

1. **Prévisions Open-Meteo** : proportion de jours avec pluie dans la fenêtre
   future (information directe sur les prochains jours).
2. **Chaînes de Markov** : probabilités de transition calculées sur l'historique
   (si il a plu hier, quelle est la probabilité d'une pluie aujourd'hui ?).

**Combinaison pondérée :**
```
P_combinée = 0.7 × P_prevision + 0.3 × P_markov
```

Ce ratio donne plus de poids aux prévisions récentes tout en intégrant la
tendance historique.

---

## Indice de sécheresse (SPI)

Le Standardized Precipitation Index (SPI) mesure l'écart des précipitations
d'une période par rapport à la normale historique, exprimé en nombre
d'écarts-types.

**Formule (approximation Z-Score) :**
```
SPI = (P_période - P_moyenne) / σ_précipitations
```

Un SPI < -1.0 indique une période sèche, un SPI < -1.5 une sécheresse marquée.

### Échelle de sévérité

| SPI | Sévérité | Implication agronomique |
|-----|---------|------------------------|
| > -0.5 | `no_drought` | Conditions normales |
| -0.5 à -1.0 | `mild` | Surveillance conseillée |
| -1.0 à -1.5 | `moderate` | Stress hydrique modéré, irrigation possible |
| < -1.5 | `severe` | Risque de pertes de récolte, alerte |

---

## Méthodes d'analyse de sécheresse

| Méthode | Description | Usage recommandé |
|---------|-------------|-----------------|
| `'spi'` | Z-Score sur les précipitations | Suivi courant, simple et rapide |
| `'markov'` | Probabilité de persistance d'un état sec | Prévision à court terme (J+7) |
| `'hurst'` | Exposant de Hurst (mémoire longue) | Tendances multi-annuelles |
| `'combined'` | Combinaison pondérée des 3 méthodes | Vue d'ensemble complète |

---

## Utilisation

### Probabilité de pluie

```python
from kadi.weather import WeatherSession

session = WeatherSession(latitude=9.3333, longitude=2.6333, name="Parakou")

# Probabilité sur les 3 prochains jours (seuil : 1 mm minimum)
prob = session.rain_probability(days_ahead=3, min_rainfall_mm=1.0)

print(f"Probabilité demain : {prob['tomorrow'] * 100:.0f}%")
print(f"Message            : {prob['message']}")
print(f"Recommandation     : {prob['recommendation']}")
```

**Retour de `rain_probability` :**

| Clé | Type | Description |
|-----|------|-------------|
| `tomorrow` | `float` | Probabilité J+1 (0.0 à 1.0) |
| `message` | `str` | Résumé lisible de la situation |
| `recommendation` | `str` | Recommandation opérationnelle |

**Exemples de recommandations :**
- `"Évitez les traitements phytosanitaires — pluie probable demain."`
- `"Bon moment pour les semis — 3 jours secs prévus."`
- `"Risque de lessivage des intrants — attendez 48h."`

---

### Indice de sécheresse

```python
# SPI sur 3 mois glissants (suivi courant)
spi3 = session.drought_index(method="spi", window_months=3)
print(f"SPI 3 mois : {spi3['spi_3month']:.2f}")
print(f"Sévérité   : {spi3['drought_severity']}")

# Analyse combinée pour une vue complète
combined = session.drought_index(method="combined", window_months=6)
print(f"Indice combiné : {combined.get('combined_score', 'N/A'):.2f}")
print(f"Sévérité       : {combined['drought_severity']}")
```

**Retour de `drought_index` :**

| Clé | Type | Description |
|-----|------|-------------|
| `spi_3month` | `float` | Valeur SPI calculée |
| `drought_severity` | `str` | Niveau de sécheresse |
| `window_months` | `int` | Fenêtre temporelle utilisée |
| `method` | `str` | Méthode appliquée |

---

### Intégration avec kadi.market (Phase 4)

Le module de risque est utilisé directement par `kadi.market.logistics` pour
ajuster les coûts de transport selon les conditions climatiques.

```python
from kadi.weather import WeatherSession
from kadi.market import Market

ws = WeatherSession(latitude=9.30, longitude=2.08, name="Parakou")
marche = Market(lat=9.30, lon=2.08, location="Parakou", weather_session=ws)

# Le risque climatique entre dans le calcul logistique automatiquement
cout = marche.logistics.calculate_transfer_cost("Parakou", "Cotonou", crop="tomato")
print(f"Probabilité de pluie utilisée : {cout['prob_pluie'] * 100:.0f}%")
print(f"Gamma route effectif          : {cout['gamma_effectif']:.3f}")

# Vue synthétique du risque climatique
risque = marche.assess_climate_risk(days_ahead=7)
print(risque["recommendation"])
```

---

::: kadi.weather.risk.RiskIndicators


def analyze_fire_risk(data):
    """
    Analyse des mesures fictives du simulateur FLAME DNA.

    Seuils pédagogiques uniquement.
    Ce module n'est pas un détecteur d'incendie certifié.
    """

    temperature = float(data["temperature"])
    smoke = float(data["smoke"])
    oxygen = float(data["oxygen"])
    airflow = float(data["airflow"])

    warnings = []
    critical = []

    # Vérification des mesures
    if temperature >= 65:
        critical.append("Température simulée très élevée")
    elif temperature >= 35:
        warnings.append("Température simulée inhabituelle")

    if smoke >= 0.55:
        critical.append("Indice de fumée simulée élevé")
    elif smoke >= 0.10:
        warnings.append("Présence de fumée simulée")

    if oxygen < 19 or oxygen > 24:
        warnings.append("Concentration en oxygène inhabituelle")

    if airflow < 0.08:
        warnings.append("Ventilation simulée faible")

    # Classification de la situation
    if len(critical) >= 2:
        status = "ALERTE"
        level = 2
        message = "Alerte incendie simulée : vérification requise."

    elif critical or warnings:
        status = "ANOMALIE"
        level = 1
        message = "Anomalie détectée dans les mesures simulées."

    else:
        status = "NORMAL"
        level = 0
        message = "Aucune anomalie selon les règles du prototype."

    return {
        "status": status,
        "level": level,
        "message": message,
        "details": critical + warnings,
    }

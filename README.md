# Volet Virtuel IO pour Home Assistant

`volet_virtuel_io` est une intégration personnalisée pour Home Assistant qui permet de créer une entité `cover` (volet) virtuelle. Cette entité simule la position d'un volet roulant (de 0% à 100%) en se basant sur des temps de montée et de descente configurables. L'objectif principal est de fournir une représentation avec état de position pour des volets classiques qui sont normally contrôlés par de simples commandes de montée/descente (par exemple, via des relais, des interrupteurs, ou des scripts) sans retour d'état de position natif.

L'entité virtuelle écoute les changements d'état des entités Home Assistant existantes que vous utilisez pour commander physiquement votre volet.

## Fonctionnalités

*   **Simulation de Position :** Calcule et maintient une position virtuelle (0-100%) pour le volet.
*   **Contrôle par Entités Physiques :** Réagit à l'activation de vos entités de commande physique (montée, descente, arrêt optionnel) pour démarrer ou arrêter le mouvement simulé.
*   **Commandes Standard `cover` :** Supporte les services `open_cover`, `close_cover`, `stop_cover`, et `set_cover_position`.
*   **Temps de Parcours Configurables :** Définissez des temps distincts pour l'ouverture complète et la fermeture complète.
*   **Restauration de l'État :** La dernière position connue du volet est sauvegardée et restaurée après un redémarrage de Home Assistant.
*   **Position Initiale Configurable :** Définissez une position par défaut si aucun état n'est restauré.

## Installation

1.  **Copier les Fichiers :**
    *   Accédez au répertoire de configuration principal de votre Home Assistant (celui où se trouve `configuration.yaml`).
    *   Créez un dossier `custom_components` s'il n'existe pas déjà.
    *   Dans `custom_components`, créez un dossier `volet_virtuel_io`.
    *   Copiez les fichiers suivants de ce projet (générés précédemment) dans le dossier `custom_components/volet_virtuel_io/` :
        *   `manifest.json`
        *   `__init__.py`
        *   `cover.py`

    Votre structure de fichiers devrait être :
    ```
    <dossier_config_home_assistant>/
    |-- configuration.yaml
    |-- custom_components/
    |   |-- volet_virtuel_io/
    |       |-- __init__.py
    |       |-- manifest.json
    |       |-- cover.py
    |-- ... (autres fichiers)
    ```

## Configuration

L'intégration se configure en ajoutant une entrée à la section `cover:` de votre fichier `configuration.yaml`.

```yaml
cover:
  - platform: volet_virtuel_io
    name: "Nom de Votre Volet Virtuel"    # Ex: "Volet Salon Virtuel"
    entity_up: "ID_ENTITE_MONTEE"          # Ex: "switch.salon_volet_montee_relais"
    entity_down: "ID_ENTITE_DESCENTE"        # Ex: "input_boolean.salon_volet_descente_bouton"
    entity_stop: "ID_ENTITE_ARRET"         # Optionnel. Ex: "script.salon_volet_stop"
    travel_time_up: 30                   # Temps (secondes) pour ouverture 0% -> 100%
    travel_time_down: 28                 # Temps (secondes) pour fermeture 100% -> 0%
    initial_position: 0                  # Optionnel (défaut 50). Position (0-100) si pas d'état restauré.
```

**Paramètres de Configuration :**

*   `platform: volet_virtuel_io` (**Requis**) : Indique d'utiliser cette intégration.
*   `name` (*Optionnel*, Défaut: "Volet Virtuel IO") : Le nom convivial de l'entité `cover` (ex: `cover.nom_de_votre_volet_virtuel`).
*   `entity_up` (**Requis**) : L'ID de l'entité Home Assistant (ex: `switch.XXX`, `input_boolean.YYY`) qui commande la montée physique.
*   `entity_down` (**Requis**) : L'ID de l'entité pour la commande de descente physique.
*   `entity_stop` (*Optionnel*) : L'ID de l'entité pour la commande d'arrêt physique. Si omis, l'arrêt est géré par la désactivation de `entity_up` ou `entity_down` pendant un mouvement.
*   `travel_time_up` (*Optionnel*, Défaut: 30) : Temps en secondes pour l'ouverture complète (0% à 100%).
*   `travel_time_down` (*Optionnel*, Défaut: 30) : Temps en secondes pour la fermeture complète (100% à 0%).
*   `initial_position` (*Optionnel*, Défaut: 50) : Position (0-100) au premier démarrage si aucun état n'est restauré (0 = fermé, 100 = ouvert).

**Exemple :**
```yaml
cover:
  - platform: volet_virtuel_io
    name: "Volet Bureau IO"
    entity_up: "input_boolean.bureau_montee_btn"
    entity_down: "input_boolean.bureau_descente_btn"
    entity_stop: "input_boolean.bureau_stop_btn"
    travel_time_up: 25
    travel_time_down: 22
    initial_position: 100
```

## Vérification et Redémarrage

1.  Après avoir modifié `configuration.yaml`, allez dans **Outils de développement** > **YAML** (Interface HA).
2.  Cliquez **VÉRIFIER LA CONFIGURATION**. Corrigez les erreurs.
3.  Si valide, **REDÉMARREZ Home Assistant**.

## Utilisation

*   Une nouvelle entité `cover` (ex: `cover.nom_de_votre_volet_virtuel`) sera créée.
*   **Contrôle via UI HA :** Utilisez les commandes Ouvrir/Fermer/Stop/Position.
    *   **Note :** L'entité virtuelle elle-même ne commande pas vos relais/interrupteurs physiques. Elle simule la position. Pour que le virtuel commande le matériel, créez des automatisations HA séparées.
*   **Réaction aux commandes physiques :** L'activation de `entity_up`, `entity_down`, `entity_stop` affectera l'état et la position du volet virtuel.
*   **Restauration de l'état :** La position est sauvegardée et restaurée après redémarrage.
*   **Attributs :** L'entité expose des attributs comme `target_position`, temps de parcours, entités liées.

## Dépannage

*   Vérifiez les IDs d'entités dans `configuration.yaml`.
*   Consultez les journaux HA (**Paramètres** > **Système** > **Journaux**) pour les messages de `volet_virtuel_io`.

---
*(Ce README est généré et peut être adapté pour un dépôt Git.)*
<!-- ========================================================================== -->
<!-- File Name:   README.md                                                     -->
<!-- Version:     4.22.0                                                        -->
<!-- Date:        2026-11-11                                                    -->
<!-- Author:      Oleh Riabtsev                                                 -->
<!-- Description: Bilingual (DE / EN) production deployment, configuration,     -->
<!--              and CI/CD operations guide for VeRO Integration Service.      -->
<!-- ========================================================================== -->

# VeRO Integration Service (DSpace-CRIS ↔ d.3 DMS)

[🇩🇪 Deutsch](#-deutsche-version) | [🇬🇧 English](#-english-version)

---

## Repository-Struktur / Repository Structure

```text
/opt/vero-integration/
├── app/                                        # Produktionsmodule / Production modules
│   ├── config_loader.py                        # Konfigurations-Loader / Configuration loader
│   ├── config.cfg                              # Produktivkonfiguration (nicht in Git) / Active config (gitignored)
│   ├── d3_api_client.py                        # d.3 DMS REST-API-Client / d.3 DMS REST API client
│   ├── d3_dspace_status_checker.py             # Statusprüfung & Rücksynchronisation / Status & back-sync checker
│   ├── dspace_pool_pdf_batch_processor_input.py # Hauptdienst (Entrypoint) / Main daemon entrypoint
│   ├── dspace_scan_pool_details.py             # DSpace-Pool- & Metadaten-Scanner / DSpace pool & metadata scanner
│   ├── dspace_to_d3_mapper.py                  # Feld-Mapping DSpace -> d.3 / Metadata field mapper
│   ├── generate_pdf_report.py                  # PDF-Meldebogen-Generator / PDF Meldebogen generator
│   ├── i18n.py                                 # Mehrsprachigkeit (DE/EN/RU) / Localization (DE/EN/RU)
│   └── requirements.txt                        # Python-Abhängigkeiten (Python 3.10+) / Python dependencies
├── generated_pdf_meldebogen/                   # Ausgabepuffer für PDFs / Generated PDF buffer
├── logs/                                       # Rotierende Dienstprotokolle / Rotating service logs
├── .venv/                                      # Isolierte Python-Umgebung / Isolated Python venv
├── config.cfg.template                         # Bereinigte Konfigurationsvorlage / Sanitized config template
├── install.sh                                  # Linux-Installationsskript / Automated Linux installer
├── vero-integration.service                    # systemd-Unit-Datei / systemd service unit
└── README.md                                   # Administrationshandbuch (DE/EN) / Admin guide (DE/EN)
```

---

## 🇩🇪 Deutsche Version

Hintergrunddienst (Daemon) zur automatisierten bidirektionalen Synchronisation zwischen **DSpace-CRIS (VeRO)** und **d.3 DMS**. Der Dienst überwacht Workflow-Warteschlangen (`pooltasks` / `claimedtasks`), erzeugt PDF-Meldebögen, legt Drittmittelakten in d.3 DMS an und gleicht Freigabestatus sowie SAP-Kostenstellen für **Application**- (Anträge) und **Funding**-Objekte (Bewilligungen) ab.

### 1. Vorbereitung in DSpace-CRIS (VeRO)

#### 1.1. Erstellung des Bot-Dienstkontos (EPerson)
1. Melden Sie sich im DSpace-CRIS-Administrationsbereich an: `https://<dspace-domain>/admin`.
2. Navigieren Sie zu **Access Control** → **EPeople** (*Zugriffskontrolle → Benutzer*).
3. Klicken Sie auf **Add EPerson** und tragen Sie folgende Werte ein:
   * **Email:** `vero-bot@uni-vechta.de`
   * **First Name:** `VeRO`
   * **Last Name:** `Bot Integration`
   * **Can Log In:** aktivieren (`True`)
   * **Require Certificate:** deaktivieren (`False`)
4. Klicken Sie auf **Save**, anschließend auf **Set Password**, vergeben Sie ein sicheres Kennwort und hinterlegen Sie dieses später in der `config.cfg`.

#### 1.2. XML-Workflow-Konfiguration auf dem DSpace-Server
Der Integrationsschritt `externalApprovalStep` wird nach den menschlichen Prüfschritten und unmittelbar vor der finalen Archivierung (`checkcorrectionstep`) ausgeführt.

Bearbeiten Sie die Datei `[dspace]/config/spring/api/workflow.xml`:
1. Verknüpfen Sie die Handles der Ziel-Sammlungen (*Application* und *Funding*) im Bean `XmlWorkflowFactoryImpl` mit `customExternalWorkflow`:
   ```xml
   <bean class="org.dspace.xmlworkflow.XmlWorkflowFactoryImpl">
       <property name="workflowMapping">
           <util:map>
               <entry key="defaultWorkflow" value-ref="defaultWorkflow"/>
               <entry key="123456789/22" value-ref="customExternalWorkflow"/>
               <entry key="123456789/25" value-ref="customExternalWorkflow"/>
               <entry key="123456789/26" value-ref="customExternalWorkflow"/>
               <entry key="123456789/4"  value-ref="customExternalWorkflow"/>
           </util:map>
       </property>
   </bean>
   ```
2. Stellen Sie sicher, dass die Schrittfolge in `customExternalWorkflow` den Schritt `externalApprovalStep` enthält:
   ```xml
   <bean name="customExternalWorkflow" class="org.dspace.xmlworkflow.state.Workflow">
       <property name="firstStep" ref="customReviewStep"/>
       <property name="steps">
           <util:list>
               <ref bean="customReviewStep"/>
               <ref bean="customEditStep"/>
               <ref bean="customFinalEditStep"/>
               <ref bean="externalApprovalStep"/>
               <ref bean="checkcorrectionstep"/>
           </util:list>
       </property>
   </bean>
   ```
3. Registrieren Sie die Rolle `externalApprovalRole` und den Schritt `externalApprovalStep`:
   ```xml
   <bean id="externalApprovalRole" class="org.dspace.xmlworkflow.Role">
       <property name="scope" value="#{ T(org.dspace.xmlworkflow.Role.Scope).COLLECTION}"/>
       <property name="name" value="Workflow_Step_VeRO_Bot"/>
       <property name="description" value="Automated VeRO bot for d.3 DMS integration"/>
   </bean>

   <bean name="externalApprovalStep" class="org.dspace.xmlworkflow.state.Step">
       <property name="userSelectionMethod" ref="claimaction"/>
       <property name="role" ref="externalApprovalRole"/>
       <property name="outcomes">
           <util:map>
               <entry key="#{ T(org.dspace.xmlworkflow.state.actions.ActionResult).OUTCOME_COMPLETE}"
                      value-ref="checkcorrectionstep"/>
           </util:map>
       </property>
       <property name="actions">
           <list>
               <ref bean="editaction"/>
           </list>
       </property>
   </bean>
   ```
4. Starten Sie Tomcat neu:
   ```bash
   sudo systemctl restart tomcat
   ```

#### 1.3. Zuweisung der Bot-Rolle in den Ziel-Sammlungen
Nach dem Neustart generiert DSpace automatisch sammlungsbezogene Gruppen nach dem Muster `COLLECTION_<UUID>_WORKFLOW_ROLE_externalApprovalRole`.
1. Öffnen Sie die Ziel-Sammlung (z. B. *Anträge*):  
   `https://<dspace-domain>/communities/<UUID>/collections/<UUID>`
2. Klicken Sie auf **Edit Collection** → Reiter **Roles**.
3. Klicken Sie in der Zeile **`externalApprovalRole`** auf **Edit Group** (bzw. **Create Group**).
4. Suchen Sie nach `vero-bot@uni-vechta.de`, fügen Sie das Dienstkonto der Gruppe hinzu und klicken Sie auf **Save**.
5. Wiederholen Sie diesen Vorgang für alle weiteren Sammlungen, die `customExternalWorkflow` verwenden.

---

### 2. Voraussetzungen in d.3 DMS

Stellen Sie vor dem Start des Dienstes sicher, dass in d.3 DMS folgende Strukturen eingerichtet sind:
* **Aktenkategorie:** `ADRIT` (*Drittmittelakte*).
* **Vorgangsordner:**
  * `/009` — Antragsunterlagen (*Antragsunterlagen / Meldebogen*).
  * `/002` — Bewilligungsunterlagen (*Bewilligung, Änderung, Bescheid*).
* **Metadatenfelder (Objekteigenschaften):**
  * Feld `514` (`Vero_ID`) — unveränderliche 36-stellige DSpace-UUID.
  * Feld `515` (`Vero_Status`) — Workflow-Status (`Antrag_eingegangen`, `DMV_geprueft`, `Praesidium_Ja`, `Praesidium_Nein`, `Kostenstelle_vergeben`, `VPPF_abgelehnt`).
  * Feld `516` (bzw. `9` / `Aktentitel`) — SAP-Fonds / *Kostenstelle*.
  * Feld `517` (`Finanzstelle`) — SAP-Finanzstelle.
* **API-Zugriff:** Gültiger Bearer Token (`api_key`) mit Lese- und Schreibrechten für das Ziel-Repository (`repo_id`).

---

### 3. Installation auf dem Linux-Server (Ubuntu 22.04 / 24.04 LTS, Debian 11 / 12)

#### 3.1. Systempakete installieren und Repository klonen
```bash
sudo apt-get update && sudo apt-get install -y python3 python3-venv python3-pip git curl
cd /opt
sudo git clone [https://github.com/MasterUaKi/vero_linux_release.git](https://github.com/MasterUaKi/vero_linux_release.git) vero-integration
cd /opt/vero-integration
```

#### 3.2. Automatischen Installer ausführen
```bash
sudo bash install.sh
```
Das Skript `install.sh` übernimmt vollständig:
* die Anlage des Systembenutzers `vero-bot` ohne interaktive Shell (`/bin/false`);
* die Erstellung von `/opt/vero-integration/app`, `/opt/vero-integration/logs` und `/opt/vero-integration/generated_pdf_meldebogen`;
* das Kopieren von `config.cfg.template` nach `/opt/vero-integration/app/config.cfg` (falls noch nicht vorhanden);
* die Rechtevergabe `750` für `vero-bot:vero-bot` sowie die Deaktivierung der Dateimodus-Überwachung in Git (`git config core.fileMode false`);
* die Einrichtung der virtuellen Python-Umgebung `/opt/vero-integration/.venv` und Installation von `app/requirements.txt`;
* die Registrierung und Aktivierung von `vero-integration.service` in `systemd`.

#### 3.3. Produktivkonfiguration anpassen (`app/config.cfg`)
Öffnen Sie die Konfigurationsdatei:
```bash
sudo nano /opt/vero-integration/app/config.cfg
```
Tragen Sie die Zugangsdaten Ihrer Umgebung ein:
```ini
[DSPACE]
base_url = [https://vero.uni-vechta.de/server/api](https://vero.uni-vechta.de/server/api)
bot_email = vero-bot@uni-vechta.de
bot_password = IHR_BOT_KENNWORT
request_delay = 1.0

[D3DMS]
url = [https://ecm-apps.uni-vechta.de](https://ecm-apps.uni-vechta.de)
api_key = IHR_D3_API_KEY
repo_id = f1e1b294-5602-5d8e-8985-e6d0c944b113
folder_application = 009
folder_funding = 002
request_delay = 1.5

[PATHS]
t_drive_dir = generated_pdf_meldebogen

[D3_DEFAULTS]
zda = Nein
aussonderung = B
aufbewahrungsfrist = 120
vero_status = Antrag_eingegangen

[SETTINGS]
poll_interval_seconds = 60
language = de

[LOGGING]
log_dir = /opt/vero-integration/logs
log_filename = vero_integration.log
backup_count = 30
```

---

### 4. Dienstverwaltung und Überwachung

* **Dienst starten:**
  ```bash
  sudo systemctl start vero-integration.service
  ```
* **Status prüfen:**
  ```bash
  sudo systemctl status vero-integration.service
  ```
* **Systemprotokoll live verfolgen:**
  ```bash
  sudo journalctl -u vero-integration.service -f
  ```
* **Anwendungs-Logdatei einsehen:**
  ```bash
  sudo tail -n 50 /opt/vero-integration/logs/vero_integration.log
  ```
* **Neustart und Stopp:**
  ```bash
  sudo systemctl restart vero-integration.service
  sudo systemctl stop vero-integration.service
  ```

---

### 5. Update-Pipeline (CI/CD)

#### Schritt 1: Release-Veröffentlichung von der Entwickler-Workstation (Windows)
Das Skript `sync_to_release.py` überträgt die Produktionsmodule aus `d3dmsprobe` nach `vero_linux_release`, bereinigt Kennwörter bei der Erzeugung von `config.cfg.template`, setzt die Linux-Pfade und überträgt den Commit nach GitHub:
```powershell
python C:\Users\oriabtsev\PycharmProjects\d3dms\d3dmsprobe\sync_to_release.py --push -m "feat: release description"
```

#### Schritt 2: Aktualisierung auf dem Linux-Server einspielen
Rufen Sie die Änderungen unter dem Verzeichniseigentümer `vero-bot` ab und starten Sie den Dienst neu (die produktive `app/config.cfg` bleibt unangetastet):
```bash
sudo -u vero-bot git -C /opt/vero-integration pull origin main && sudo systemctl restart vero-integration.service
```
*(Falls `app/requirements.txt` geändert wurde, aktualisieren Sie zusätzlich die Pakete in `.venv`)*:
```bash
sudo -u vero-bot /opt/vero-integration/.venv/bin/pip install --no-cache-dir -r /opt/vero-integration/app/requirements.txt
```

---

## 🇬🇧 English Version

Background system daemon for automated bidirectional synchronization between **DSpace-CRIS (VeRO)** and **d.3 DMS**. The service monitors DSpace workflow queues (`pooltasks` / `claimedtasks`), generates summary PDF reports (*Meldebogen*), creates and updates dossiers in d.3 DMS, and synchronizes approval statuses and SAP cost centers (*Kostenstelle*) for **Application** and **Funding** entities.

### 1. DSpace-CRIS (VeRO) Prerequisites

#### 1.1. Create the Service Bot Account (EPerson)
1. Log in to the DSpace-CRIS admin console: `https://<dspace-domain>/admin`.
2. Navigate to **Access Control** → **EPeople**.
3. Click **Add EPerson** and configure the account:
   * **Email:** `vero-bot@uni-vechta.de`
   * **First Name:** `VeRO`
   * **Last Name:** `Bot Integration`
   * **Can Log In:** enabled (`True`)
   * **Require Certificate:** disabled (`False`)
4. Click **Save**, then click **Set Password**, define a strong password, and record it for `config.cfg`.

#### 1.2. Configure the XML Workflow on the DSpace Server
The integration step `externalApprovalStep` executes after human review stages and directly before final archiving (`checkcorrectionstep`).

Edit `[dspace]/config/spring/api/workflow.xml`:
1. Map target collection handles (*Application* and *Funding*) to `customExternalWorkflow` inside `XmlWorkflowFactoryImpl`:
   ```xml
   <bean class="org.dspace.xmlworkflow.XmlWorkflowFactoryImpl">
       <property name="workflowMapping">
           <util:map>
               <entry key="defaultWorkflow" value-ref="defaultWorkflow"/>
               <entry key="123456789/22" value-ref="customExternalWorkflow"/>
               <entry key="123456789/25" value-ref="customExternalWorkflow"/>
               <entry key="123456789/26" value-ref="customExternalWorkflow"/>
               <entry key="123456789/4"  value-ref="customExternalWorkflow"/>
           </util:map>
       </property>
   </bean>
   ```
2. Verify that `customExternalWorkflow` includes `externalApprovalStep`:
   ```xml
   <bean name="customExternalWorkflow" class="org.dspace.xmlworkflow.state.Workflow">
       <property name="firstStep" ref="customReviewStep"/>
       <property name="steps">
           <util:list>
               <ref bean="customReviewStep"/>
               <ref bean="customEditStep"/>
               <ref bean="customFinalEditStep"/>
               <ref bean="externalApprovalStep"/>
               <ref bean="checkcorrectionstep"/>
           </util:list>
       </property>
   </bean>
   ```
3. Define the `externalApprovalRole` bean and `externalApprovalStep`:
   ```xml
   <bean id="externalApprovalRole" class="org.dspace.xmlworkflow.Role">
       <property name="scope" value="#{ T(org.dspace.xmlworkflow.Role.Scope).COLLECTION}"/>
       <property name="name" value="Workflow_Step_VeRO_Bot"/>
       <property name="description" value="Automated VeRO bot for d.3 DMS integration"/>
   </bean>

   <bean name="externalApprovalStep" class="org.dspace.xmlworkflow.state.Step">
       <property name="userSelectionMethod" ref="claimaction"/>
       <property name="role" ref="externalApprovalRole"/>
       <property name="outcomes">
           <util:map>
               <entry key="#{ T(org.dspace.xmlworkflow.state.actions.ActionResult).OUTCOME_COMPLETE}"
                      value-ref="checkcorrectionstep"/>
           </util:map>
       </property>
       <property name="actions">
           <list>
               <ref bean="editaction"/>
           </list>
       </property>
   </bean>
   ```
4. Restart Tomcat:
   ```bash
   sudo systemctl restart tomcat
   ```

#### 1.3. Assign the Bot Role to Target Collections
Upon restart, DSpace automatically creates collection-scoped groups named `COLLECTION_<UUID>_WORKFLOW_ROLE_externalApprovalRole`.
1. Open the target collection page (e.g., *Anträge*):  
   `https://<dspace-domain>/communities/<UUID>/collections/<UUID>`
2. Click **Edit Collection** → open the **Roles** tab.
3. In the **`externalApprovalRole`** row, click **Edit Group** (or **Create Group**).
4. Search for `vero-bot@uni-vechta.de`, add the user to the group, and click **Save**.
5. Repeat for all remaining collections mapped to `customExternalWorkflow`.

---

### 2. d.3 DMS Prerequisites

Ensure the following schema items are configured in d.3 DMS before starting the daemon:
* **Dossier Category:** `ADRIT` (*Drittmittelakte*).
* **Folder Structure (*Vorgänge*):**
  * `/009` — Application documents (*Antragsunterlagen / Meldebogen*).
  * `/002` — Funding decision documents (*Bewilligung, Änderung, Bescheid*).
* **Metadata Fields (Object Properties):**
  * `514` (`Vero_ID`) — persistent 36-character DSpace UUID.
  * `515` (`Vero_Status`) — workflow states (`Antrag_eingegangen`, `DMV_geprueft`, `Praesidium_Ja`, `Praesidium_Nein`, `Kostenstelle_vergeben`, `VPPF_abgelehnt`).
  * `516` (or `9` / `Aktentitel`) — SAP fund / *Kostenstelle*.
  * `517` (`Finanzstelle`) — SAP Financial Center ID.
* **API Authentication:** Active Bearer Token (`api_key`) with read and write permissions for the target repository (`repo_id`).

---

### 3. Linux Server Installation (Ubuntu 22.04 / 24.04 LTS, Debian 11 / 12)

#### 3.1. Install System Dependencies and Clone the Repository
```bash
sudo apt-get update && sudo apt-get install -y python3 python3-venv python3-pip git curl
cd /opt
sudo git clone [https://github.com/MasterUaKi/vero_linux_release.git](https://github.com/MasterUaKi/vero_linux_release.git) vero-integration
cd /opt/vero-integration
```

#### 3.2. Run the Automated Installer
```bash
sudo bash install.sh
```
The `install.sh` script automates environment provisioning:
* creates system user `vero-bot` without interactive login (`/bin/false`);
* creates `/opt/vero-integration/app`, `/opt/vero-integration/logs`, and `/opt/vero-integration/generated_pdf_meldebogen`;
* copies `config.cfg.template` to `/opt/vero-integration/app/config.cfg` (if not already present);
* enforces `750` permissions owned by `vero-bot:vero-bot` and disables file mode tracking in Git (`git config core.fileMode false`);
* provisions `/opt/vero-integration/.venv` and installs dependencies from `app/requirements.txt`;
* registers and enables `vero-integration.service` in `systemd`.

#### 3.3. Configure Production Settings (`app/config.cfg`)
Open the configuration file:
```bash
sudo nano /opt/vero-integration/app/config.cfg
```
Set your environment credentials and endpoints:
```ini
[DSPACE]
base_url = [https://vero.uni-vechta.de/server/api](https://vero.uni-vechta.de/server/api)
bot_email = vero-bot@uni-vechta.de
bot_password = YOUR_BOT_PASSWORD
request_delay = 1.0

[D3DMS]
url = [https://ecm-apps.uni-vechta.de](https://ecm-apps.uni-vechta.de)
api_key = YOUR_D3_API_KEY
repo_id = f1e1b294-5602-5d8e-8985-e6d0c944b113
folder_application = 009
folder_funding = 002
request_delay = 1.5

[PATHS]
t_drive_dir = generated_pdf_meldebogen

[D3_DEFAULTS]
zda = Nein
aussonderung = B
aufbewahrungsfrist = 120
vero_status = Antrag_eingegangen

[SETTINGS]
poll_interval_seconds = 60
language = de

[LOGGING]
log_dir = /opt/vero-integration/logs
log_filename = vero_integration.log
backup_count = 30
```

---

### 4. Service Operations and Monitoring

* **Start service:**
  ```bash
  sudo systemctl start vero-integration.service
  ```
* **Check status:**
  ```bash
  sudo systemctl status vero-integration.service
  ```
* **Follow systemd journal live:**
  ```bash
  sudo journalctl -u vero-integration.service -f
  ```
* **Read application log file:**
  ```bash
  sudo tail -n 50 /opt/vero-integration/logs/vero_integration.log
  ```
* **Restart and stop:**
  ```bash
  sudo systemctl restart vero-integration.service
  sudo systemctl stop vero-integration.service
  ```

---

### 5. Update Pipeline (CI/CD)

#### Step 1: Publish Release from Developer Workstation (Windows)
The `sync_to_release.py` script copies production modules from `d3dmsprobe` to `vero_linux_release`, strips secrets when generating `config.cfg.template`, enforces Linux paths, and pushes the commit to GitHub:
```powershell
python C:\Users\oriabtsev\PycharmProjects\d3dms\d3dmsprobe\sync_to_release.py --push -m "feat: release description"
```

#### Step 2: Apply Update on the Linux Server
Pull changes as directory owner `vero-bot` and restart the daemon (`app/config.cfg` remains untouched):
```bash
sudo -u vero-bot git -C /opt/vero-integration pull origin main && sudo systemctl restart vero-integration.service
```
*(If `app/requirements.txt` was updated, refresh `.venv` packages)*:
```bash
sudo -u vero-bot /opt/vero-integration/.venv/bin/pip install --no-cache-dir -r /opt/vero-integration/app/requirements.txt
```
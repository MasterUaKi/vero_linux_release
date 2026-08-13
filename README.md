Markdown

\# VeRO Integration Service (DSpace CRIS ↔ d.3 DMS)



🌍 \*\*Languages:\*\* \[Deutsch](#-deutsche-version) | \[Русский](#-русская-версия)



\---



\## 🇩🇪 DEUTSCHE VERSION



Daemon-Dienst zur automatischen Synchronisierung von Anträgen (Application) und Finanzierungen (Funding) zwischen DSpace CRIS und dem Dokumentenmanagementsystem d.3 DMS.



\### Abschnitt 1. Vorbereitung der Dienstkonten und Berechtigungen



\*\*1.1. Erstellung des Bot-Kontos in DSpace\*\*

1\. Melden Sie sich im DSpace-Administrationsbereich an: `https://<ihre-dspace-domain>/admin`.

2\. Navigieren Sie zu \*\*Access Control -> EPeople\*\*.

3\. Klicken Sie auf \*\*Add EPerson\*\* und füllen Sie die Daten aus:

&#x20;  \* \*\*Email:\*\* Geben Sie die E-Mail-Adresse des Bots ein (z. B. `vero-bot@uni-vechta.de`).

&#x20;  \* \*\*First Name / Last Name:\*\* `VeRO` / `Bot Integration`.

&#x20;  \* \*\*Can Log In:\*\* Setzen Sie das Häkchen (`True`).

&#x20;  \* \*\*Require Certificate / Self Registered:\*\* Leer lassen (`False`).

4\. Vergeben Sie ein sicheres Passwort für das Profil und speichern Sie die Änderungen.



\*\*1.2. Workflow-Konfiguration in DSpace\*\*

1\. Navigieren Sie zu \*\*Access Control -> Groups\*\*.

2\. Erstellen Sie die Gruppe `Workflow\_Step\_VeRO\_Bot`.

3\. Fügen Sie den erstellten Benutzer (`vero-bot`) zu dieser Gruppe hinzu, damit der Bot die Aufgaben im Pool (pooltasks) sehen kann.



\*\*1.3. Vorbereitung der Attribute in d.3 DMS\*\*

1\. Generieren Sie in der d.3 DMS-Administrationskonsole einen Service-API-Schlüssel (Bearer Token). 

2\. Halten Sie die folgenden Daten bereit: API-Schlüssel, Repository-ID (`repo\_id`).

3\. Stellen Sie sicher, dass im System eine Dokumenteneigenschaft mit der ID `515` (oder dem technischen Namen `Vero\_Status`) existiert.



\### Abschnitt 2. Vorbereitung des Linux-Servers

Der Dienst ist für den Betrieb auf einem Server unter \*\*Ubuntu Linux (22.04 / 24.04 LTS)\*\* oder \*\*Debian (11 / 12)\*\* ausgelegt.



\*\*Installation grundlegender Abhängigkeiten\*\*

Verbinden Sie sich per SSH mit dem Server und installieren Sie Python 3 (Version 3.10+) und Git:

```bash

sudo apt-get update

sudo apt-get upgrade -y

sudo apt-get install -y python3 python3-venv python3-pip git

Abschnitt 3. Repository klonen und Basiskonfiguration

Laden Sie den Code aus dem Release-Repository herunter (empfohlen im Verzeichnis /opt):



Bash

cd /opt

sudo git clone \[https://github.com/MasterUaKi/vero\_linux\_release.git](https://github.com/MasterUaKi/vero\_linux\_release.git) vero-integration

cd /opt/vero-integration

Erstellen Sie die Konfigurationsdatei aus der Vorlage:



Bash

sudo cp config.cfg.template app/config.cfg

Abschnitt 4. Konfiguration der Dienstparameter (config.cfg)

Öffnen Sie die Datei in einem Texteditor:



Bash

sudo nano /opt/vero-integration/app/config.cfg

Füllen Sie die Abschnitte mit den Daten Ihrer Umgebung aus:



Ini, TOML

\[DSPACE]

base\_url = \[https://dspace.your-domain.de/server/api](https://dspace.your-domain.de/server/api)

bot\_email = vero-bot@uni-vechta.de

bot\_password = YOUR\_SECURE\_BOT\_PASSWORD

request\_delay = 1.0



\[D3DMS]

url = \[https://ecm-apps.your-domain.de](https://ecm-apps.your-domain.de)

api\_key = YOUR\_D3\_API\_KEY

repo\_id = YOUR\_D3\_REPO\_GUID

folder\_application = 009

folder\_funding = 002

request\_delay = 1.5



\[SETTINGS]

poll\_interval\_seconds = 360

language = de

Abschnitt 5. Installation und Start des Hintergrunddienstes

Im Repository befindet sich ein automatischer Installer, der einen Systembenutzer erstellt und den Dienst in den Linux-Autostart einträgt.



Bash

cd /opt/vero-integration

sudo bash install.sh

Dienstverwaltung (systemd):



Bash

sudo systemctl status vero-integration.service

sudo systemctl stop vero-integration.service

sudo systemctl restart vero-integration.service

Protokolle anzeigen:



Bash

tail -f /opt/vero-integration/logs/vero\_integration.log

Abschnitt 6. Dienst auf eine neue Version aktualisieren

Ihre ausgefüllte config.cfg-Datei wird beim Update nicht gelöscht.



Bash

sudo systemctl stop vero-integration.service

cd /opt/vero-integration

sudo git pull origin main

sudo /opt/vero-integration/.venv/bin/pip install -r /opt/vero-integration/requirements.txt

sudo systemctl start vero-integration.service

Anhang A. Konfiguration des XML Workflows in DSpace

Damit der Bot Anträge in seinen Pool erhält, binden Sie ihn in die Datei \[dspace-src]/dspace/config/spring/api/workflow.xml ein (Tomcat-Neustart erforderlich).



1\. Bot-Rolle und Schritt-Definition:



XML

<bean id="externalApprovalRole" class="org.dspace.xmlworkflow.Role">

&#x20;   <property name="scope" value="#{ T(org.dspace.xmlworkflow.Role.Scope).COLLECTION}"/>

&#x20;   <property name="name" value="Workflow\_Step\_VeRO\_Bot"/>

&#x20;   <property name="description" value="Automated VeRO bot for d.3 DMS integration"/>

</bean>



<bean name="externalApprovalStep" class="org.dspace.xmlworkflow.state.Step">

&#x20;   <property name="userSelectionMethod" ref="claimaction"/>

&#x20;   <property name="role" ref="externalApprovalRole"/>

&#x20;   <property name="outcomes">

&#x20;       <util:map>

&#x20;           <entry key="#{ T(org.dspace.xmlworkflow.state.actions.ActionResult).OUTCOME\_COMPLETE}" value-ref="checkcorrectionstep"/>

&#x20;       </util:map>

&#x20;   </property>

&#x20;   <property name="actions">

&#x20;       <list>

&#x20;           <ref bean="reviewaction"/> 

&#x20;       </list>

&#x20;   </property>

</bean>

2\. Integration in den Workflow:



XML

<bean name="customExternalWorkflow" class="org.dspace.xmlworkflow.state.Workflow">

&#x20;   <property name="firstStep" ref="customReviewStep"/>

&#x20;   <property name="steps">

&#x20;       <util:list>

&#x20;           <!-- ... andere Schritte ... -->

&#x20;           <ref bean="externalApprovalStep"/>

&#x20;           <ref bean="checkcorrectionstep"/>

&#x20;       </util:list>

&#x20;   </property>

</bean>


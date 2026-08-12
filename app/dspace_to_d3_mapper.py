# ==============================================================================
# Script Name: dspace_to_d3_mapper.py
# Version:     3.1.0
# Date:        2026-08-03
# Author:      Oleh Riabtsev / AI Assistant
# Description: Full field transformation module mapping DSpace-CRIS (VeRO)
#              metadata to d.3 DMS properties payload and PDF generation schema.
#              UPDATED: Integrated centralized default settings from config_loader.py.
# ==============================================================================

import json
import logging

from config_loader import (
    DEFAULT_ZDA,
    DEFAULT_AUSSONDERUNG,
    DEFAULT_AUFBEWAHRUNGSFRIST,
    DEFAULT_VERO_STATUS,
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)


class DSpaceToD3Mapper:
    DEFAULT_ZDA = DEFAULT_ZDA
    DEFAULT_AUSSONDERUNG = DEFAULT_AUSSONDERUNG
    DEFAULT_AUFBEWAHRUNGSFRIST = DEFAULT_AUFBEWAHRUNGSFRIST
    DEFAULT_VERO_STATUS = DEFAULT_VERO_STATUS

    TYPE_CONFIG_MATRIX = {
        "FACULTY_1": {
            "display_name": "Application Faculty 1",
            "federfuehrende_oe": "Fakultät I",
            "fakultaet_einrichtung": "Fakultät I - Bildungs- und Kulturwissenschaften",
        },
        "FACULTY_2": {
            "display_name": "Application Faculty 2",
            "federfuehrende_oe": "Fakultät II",
            "fakultaet_einrichtung": "Fakultät II - Agrar- und Umweltwissenschaften",
        },
        "FUNDING": {
            "display_name": "Funding / Drittmittel",
            "federfuehrende_oe": "Drittmittelverwaltung",
            "fakultaet_einrichtung": "Referat für Forschung und Nachwuchsförderung",
        },
        "OTHER": {
            "display_name": "Application Other",
            "federfuehrende_oe": "Drittmittelverwaltung",
            "fakultaet_einrichtung": "Zentrale Einrichtung / Sonstige",
        }
    }

    @staticmethod
    def _truncate_for_d3(val: str, max_len: int = 250) -> str:
        if not val:
            return ""
        s = str(val).strip()
        return s[:max_len] if len(s) > max_len else s

    @staticmethod
    def _extract_first(metadata_dict: dict, key: str, default: str = "") -> str:
        if key in metadata_dict:
            values = metadata_dict[key]
            if isinstance(values, list) and len(values) > 0:
                return str(values[0]).strip()
        key_lower = key.lower()
        for k, values in metadata_dict.items():
            if k.lower() == key_lower and isinstance(values, list) and len(values) > 0:
                return str(values[0]).strip()
        return default

    @staticmethod
    def _extract_all(metadata_dict: dict, key: str) -> list:
        key_lower = key.lower()
        for k, values in metadata_dict.items():
            if k.lower() == key_lower and isinstance(values, list):
                return [str(v).strip() for v in values if str(v).strip()]
        return []

    @classmethod
    def build_aktenplanzeichen(cls, dspace_item_details: dict) -> str:
        """
        Динамическое формирование Aktenplanzeichen по правилам Андреаса:
        - Antragsforschung: 11.01.0.[JAHR]
        - Auftragsforschung: 11.01.1.[JAHR]
        - Wissenschaftliche Weiterbildung: 11.01.2.[JAHR]
        - Sonstige betriebliche Erträge: 11.01.3.[JAHR]
        """
        metadata = dspace_item_details.get("metadata", {})

        # Проверяем как Application, так и Funding поля типов финансирования
        funding_type = (
                cls._extract_first(metadata, "veroAP.funding.type", "") or
                cls._extract_first(metadata, "veroFU.funding.type", "")
        ).lower()

        project_type = (
                cls._extract_first(metadata, "veroAP.project.type", "") or
                cls._extract_first(metadata, "veroFU.project.type", "")
        ).lower()

        title = cls._extract_first(metadata, "dc.title", "").lower()

        if "auftragsforschung" in funding_type or "auftragsforschung" in project_type:
            code = "1"
        elif "weiterbildung" in funding_type or "weiterbildung" in project_type or "weiterbildung" in title:
            code = "2"
        elif "erträge" in funding_type or "ertrag" in funding_type or "erträge" in title:
            code = "3"
        else:
            code = "0"

        # Определение года (JAHR) из даты начала
        funding_start = (
                cls._extract_first(metadata, "veroAP.funding.start", "") or
                cls._extract_first(metadata, "oairecerif.funding.startDate", "")
        )
        if len(funding_start) >= 4 and funding_start[:4].isdigit():
            year = funding_start[:4]
        else:
            year = "2026"

        return f"11.01.{code}.{year}"

    @classmethod
    def detect_application_type(cls, dspace_item_details: dict) -> str:
        metadata = dspace_item_details.get("metadata", {})
        collection_name = dspace_item_details.get("collection", {}).get("name", "").lower()
        title = cls._extract_first(metadata, "dc.title", "").lower()
        entity_type = cls._extract_first(metadata, "dspace.entity.type", "").lower()

        if entity_type == "funding" or "veroFU.application" in metadata or "oairecerif.funding.identifier" in metadata:
            return "FUNDING"

        fak_i = cls._extract_first(metadata, "veroAP.organizationUnit.FakI", "").lower()
        org_unit = cls._extract_first(metadata, "vero.OrgUnit", "").lower()
        project_type = cls._extract_first(metadata, "veroAP.project.type", "").lower()

        if "faculty 1" in collection_name or "fakultät 1" in collection_name or "fakultät i" in org_unit or fak_i:
            return "FACULTY_1"
        elif "faculty 2" in collection_name or "fakultät 2" in collection_name or "fakultät ii" in org_unit:
            return "FACULTY_2"
        elif "funding" in collection_name or "förderung" in collection_name or "funding" in project_type or "drittmittel" in title:
            return "FUNDING"
        else:
            return "OTHER"

    @classmethod
    def extract_ds_fields(cls, dspace_item_details: dict, custom_status: str = None) -> dict:
        metadata = dspace_item_details.get("metadata", {})
        item_info = dspace_item_details.get("item_info", {})
        collection_info = dspace_item_details.get("collection", {})
        submitter_info = dspace_item_details.get("submitter", {})
        wf_item_id = dspace_item_details.get("workflow_item_id")

        provenance_list = cls._extract_all(metadata, "dc.description.provenance")
        submitted_steps_text = " | ".join(provenance_list) if provenance_list else ""

        app_type = cls.detect_application_type(dspace_item_details)
        type_cfg = cls.TYPE_CONFIG_MATRIX.get(app_type, cls.TYPE_CONFIG_MATRIX["OTHER"])
        dynamic_aktenplanzeichen = cls.build_aktenplanzeichen(dspace_item_details)

        is_funding = (app_type == "FUNDING")

        # Базовый словарь полей
        fields = {
            "app_type": app_type,
            "app_type_display": type_cfg["display_name"],
            "federfuehrende_oe": type_cfg["federfuehrende_oe"],
            "fakultaet_einrichtung": type_cfg["fakultaet_einrichtung"],
            "aktenplanzeichen": dynamic_aktenplanzeichen,

            "vero_id": item_info.get("uuid") or str(wf_item_id),
            "workflow_item_id": str(wf_item_id),
            "collection_name": collection_info.get("name", ""),
            "submitter_email": submitter_info.get("email", ""),
            "vero_status": custom_status or cls.DEFAULT_VERO_STATUS,
            "submitted_steps": submitted_steps_text,
            "entity_type": cls._extract_first(metadata, "dspace.entity.type", "")
        }

        if is_funding:
            # === ИЗВЛЕЧЕНИЕ ПОЛЕЙ ДЛЯ FUNDING ===
            fields.update({
                "title": cls._extract_first(metadata, "dc.title", "Unbenannter Funding-Eintrag"),
                "acronym": cls._extract_first(metadata, "oairecerif.acronym", ""),
                "project_type": cls._extract_first(metadata, "veroFU.project.type", ""),
                "project_purpose": cls._extract_first(metadata, "veroFU.project.purpose", ""),
                "funding_start": cls._extract_first(metadata, "oairecerif.funding.startDate", ""),
                "funding_end": cls._extract_first(metadata, "oairecerif.funding.endDate", ""),

                "investigator": cls._extract_first(metadata, "veroFU.scientificLeader", ""),
                "org_unit": cls._extract_first(metadata, "vero.OrgUnit", ""),
                "institut": cls._extract_first(metadata, "vero.institut", ""),
                "coordinator": cls._extract_first(metadata, "crisfund.leadorganizations", ""),

                "funding_type": cls._extract_first(metadata, "veroFU.funding.type", ""),
                "funding_type_openaire": cls._extract_first(metadata, "dc.type", ""),
                "funding_funder": cls._extract_first(metadata, "oairecerif.funder", ""),
                "funding_funder_free": cls._extract_first(metadata, "veroFU.funding.funderfree", ""),
                "funding_program": cls._extract_first(metadata, "oairecerif.fundingParent", ""),

                "amount_granted": cls._extract_first(metadata, "oairecerif.amount", ""),
                "amount_currency": cls._extract_first(metadata, "oairecerif.amount.currency", "euro"),
                "amount_received": cls._extract_first(metadata, "veroFU.amount.received", ""),
                "sap_internal_id": cls._extract_first(metadata, "oairecerif.internalid", ""),

                "res_research_data": cls._extract_first(metadata, "veroFU.resources.researchData", ""),
                "res_pub_costs": cls._extract_first(metadata, "veroFU.resources.publicationcosts", ""),
                "res_openaccess": cls._extract_first(metadata, "veroFU.resources.openaccess", ""),
                "res_overhead": cls._extract_first(metadata, "veroFU.resources.overhead", ""),
                "funding_contrib_vec": cls._extract_first(metadata, "veroFU.funding.contributionVec", ""),
                "typevec_contribution": cls._extract_first(metadata, "veroFU.resources.TypevecContribution", ""),
                "daad_persons": cls._extract_first(metadata, "veroFU.daad", ""),

                "funding_identifier": cls._extract_first(metadata, "oairecerif.funding.identifier", ""),
                "dfg_geschaeftszeichen": cls._extract_first(metadata, "veroFU.identifier.dfgGeschaeftszeichen", ""),
                "dfg_projektnummer": cls._extract_first(metadata, "veroFU.identifier.dfgProjektnummer", ""),

                "oa_mandate": cls._extract_first(metadata, "oairecerif.oamandate", ""),
                "oa_mandate_url": cls._extract_first(metadata, "oairecerif.oamandate.url", ""),
                "embargo_lift": cls._extract_first(metadata, "veroFU.embargo.lift", ""),
            })
        else:
            # === ИЗВЛЕЧЕНИЕ ПОЛЕЙ ДЛЯ APPLICATION ===
            fields.update({
                "title": cls._extract_first(metadata, "dc.title", "Unbenannter Antrag"),
                "acronym": cls._extract_first(metadata, "veroAP.acronym", ""),
                "project_type": cls._extract_first(metadata, "veroAP.project.type", ""),
                "project_purpose": cls._extract_first(metadata, "veroAP.project.purpose", ""),
                "funding_start": cls._extract_first(metadata, "veroAP.funding.start", ""),
                "funding_end": cls._extract_first(metadata, "veroAP.funding.end", ""),

                "fak_i_unit": cls._extract_first(metadata, "veroAP.organizationUnit.FakI", ""),
                "org_unit": cls._extract_first(metadata, "vero.OrgUnit", ""),
                "institut": cls._extract_first(metadata, "vero.institut", ""),
                "investigator": cls._extract_first(metadata, "crispj.investigator", ""),
                "contact_person": cls._extract_first(metadata, "veroAP.person.contact", ""),
                "contact_email": cls._extract_first(metadata, "veroAP.email.contact", ""),
                "cooperation_org_unit": cls._extract_first(metadata, "veroAP.cooperation.organizationUnit", ""),
                "institute_alt": cls._extract_first(metadata, "veroAP.institute", ""),
                "cooperation_person": cls._extract_first(metadata, "veroAP.cooperation.person", ""),
                "cooperation_extern": cls._extract_first(metadata, "veroAP.cooperation.extern", ""),
                "lead": cls._extract_first(metadata, "veroAP.lead", ""),
                "inst_name_lead": cls._extract_first(metadata, "veroAP.instNameLead", ""),
                "consulting_researchdata": cls._extract_first(metadata, "veroAP.consulting.researchdata", ""),

                "research_subject": cls._extract_first(metadata, "veroAP.research.subject", ""),
                "crosssection_subject": cls._extract_first(metadata, "veroAP.crosssection.subject",
                                                           "") or cls._extract_first(metadata,
                                                                                     "veroAP.research.subject", ""),
                "subject_other": cls._extract_first(metadata, "veroAP.subject.other", ""),
                "abstract": cls._extract_first(metadata, "veroAP.abstract", ""),
                "personell_health_data": cls._extract_first(metadata, "veroAP.personellhealthData", ""),

                "funding_type": cls._extract_first(metadata, "veroAP.funding.type", ""),
                "funding_funder": cls._extract_first(metadata, "veroAP.funding.funderlist", ""),
                "funding_funder_free": cls._extract_first(metadata, "veroAP.funding.funderfree", ""),
                "funding_program": cls._extract_first(metadata, "veroAP.funding.programm", ""),
                "stage_deadline": cls._extract_first(metadata, "veroAP.stage.deadline", ""),

                "resources_staff": cls._extract_first(metadata, "veroAP.resources.staff", ""),
                "hr_explained": cls._extract_first(metadata, "veroAP.HRexplained", ""),
                "resources_material": cls._extract_first(metadata, "veroAP.resources.material", ""),
                "resources_subcontracting": cls._extract_first(metadata, "veroAP.resources.subcontracting", ""),
                "resources_research_data": cls._extract_first(metadata, "veroAP.resources.researchData", ""),
                "resources_pub_costs": cls._extract_first(metadata, "veroAP.resources.publicationcosts", ""),
                "resources_openaccess": cls._extract_first(metadata, "veroAP.resources.openaccess", ""),
                "resources_overhead": cls._extract_first(metadata, "veroAP.resources.overhead", ""),
                "funding_amount": cls._extract_first(metadata, "veroAP.fundingAmount", ""),
                "funding_contrib_vec": cls._extract_first(metadata, "veroAP.funding.contributionVec", ""),
                "hr_resources_vec": cls._extract_first(metadata, "veroAP.hrResourcesVec", ""),
                "resources_contrib_vec": cls._extract_first(metadata, "veroAP.resources.contributionVec", ""),
                "complementary_resources": cls._extract_first(metadata, "veroAP.complementaryressources", ""),
                "daad": cls._extract_first(metadata, "veroAP.daad", ""),
                "research_results": cls._extract_first(metadata, "veroAP.researchResults", ""),
                "project_requirements": cls._extract_first(metadata, "veroAP.projectrequirements", ""),
                "explication_requirements": cls._extract_first(metadata, "veroAP.explication.projectrequirements", ""),
                "capacities": cls._extract_first(metadata, "veroAP.capacities", ""),
                "capacities_explanation": cls._extract_first(metadata, "veroAP.capacitiesExplanation", ""),
                "facilities": cls._extract_first(metadata, "veroAP.facilities", ""),
                "firmation": cls._extract_first(metadata, "veroAP.firmation", ""),
                "consent_data": cls._extract_first(metadata, "veroAP.consent.data", ""),
            })

        return fields

    @classmethod
    def map_dspace_item_to_d3_akte_payload(cls, dspace_item_details: dict, repo_id: str,
                                           custom_status: str = None) -> dict:
        if not dspace_item_details:
            return None

        ds_fields = cls.extract_ds_fields(dspace_item_details, custom_status)
        is_funding = (ds_fields["app_type"] == "FUNDING")

        properties = [
            {"key": "9", "values": [cls._truncate_for_d3(ds_fields["vero_id"])]},
            {"key": "4", "values": [ds_fields["aktenplanzeichen"]]},
            {"key": "7", "values": [cls.DEFAULT_ZDA]},
            {"key": "14", "values": [cls.DEFAULT_AUSSONDERUNG]},
            {"key": "34", "values": [cls.DEFAULT_AUFBEWAHRUNGSFRIST]},
            {"key": "2", "values": [ds_fields["federfuehrende_oe"]]},
            {"key": "505", "values": [cls._truncate_for_d3(ds_fields["fakultaet_einrichtung"])]},
            {"key": "514", "values": [cls._truncate_for_d3(ds_fields["vero_id"])]},
            {"key": "515", "values": [cls._truncate_for_d3(ds_fields["vero_status"])]},
        ]

        if is_funding:
            optional_fields = [
                ("109", ds_fields["title"]),
                ("149", ds_fields["investigator"]),
                ("154", ds_fields["amount_granted"]),
                ("153", ds_fields["funding_funder"]),
                ("284", ds_fields["funding_start"]),
                ("285", ds_fields["funding_end"]),
                ("156", ds_fields["org_unit"]),
                ("155", ds_fields["funding_identifier"]),
            ]
        else:
            optional_fields = [
                ("109", ds_fields["title"]),
                ("149", ds_fields["investigator"]),
                ("154", ds_fields["funding_amount"]),
                ("153", ds_fields["funding_funder"]),
                ("284", ds_fields["funding_start"]),
                ("285", ds_fields["funding_end"]),
                ("156", ds_fields["contact_person"]),
                ("155", ds_fields["stage_deadline"]),
            ]

        for d3_key, ds_value in optional_fields:
            clean_val = cls._truncate_for_d3(ds_value)
            if clean_val:
                properties.append({"key": d3_key, "values": [clean_val]})

        return {
            "sourceId": f"/dms/r/{repo_id}/source",
            "sourceCategory": "ADRIT",
            "sourceProperties": {
                "properties": properties
            }
        }

    @classmethod
    def get_pdf_report_data(cls, dspace_item_details: dict) -> list:
        ds = cls.extract_ds_fields(dspace_item_details)
        app_type = ds["app_type"]
        is_funding = (app_type == "FUNDING")

        if is_funding:
            # === СТРУКТУРА PDF ДЛЯ FUNDING (Bewilligung) ===
            return [
                {
                    "group_name": "0 - Typ der Förderanzeige",
                    "fields": [
                        {"label": "Kategorie / Typ", "value": ds["app_type_display"]},
                        {"label": "Federführende OE", "value": ds["federfuehrende_oe"]},
                        {"label": "Aktenplanzeichen", "value": ds["aktenplanzeichen"]}
                    ]
                },
                {
                    "group_name": "1 - Allgemeine Projektdaten",
                    "fields": [
                        {"label": "Projektbezeichnung/Titel", "value": ds["title"]},
                        {"label": "Akronym", "value": ds["acronym"]},
                        {"label": "Projektform", "value": ds["project_type"]},
                        {"label": "Projektzweck", "value": ds["project_purpose"]},
                        {"label": "Projektstart / Start der Förderung", "value": ds["funding_start"]},
                        {"label": "Projektende / Ende der Förderung", "value": ds["funding_end"]}
                    ]
                },
                {
                    "group_name": "2 - Organisation & Verantwortlichkeiten",
                    "fields": [
                        {"label": "Wissenschaftliche Projektleitung", "value": ds["investigator"]},
                        {"label": "Organisationseinheit", "value": ds["org_unit"]},
                        {"label": "Institut", "value": ds["institut"]},
                        {"label": "Koordinierende Einrichtung", "value": ds["coordinator"]}
                    ]
                },
                {
                    "group_name": "3 - Förderdetails & Geldgeber",
                    "fields": [
                        {"label": "Art der Förderung", "value": ds["funding_type"]},
                        {"label": "Funding Type (OpenAIRE)", "value": ds["funding_type_openaire"]},
                        {"label": "Fördermittelgeber", "value": ds["funding_funder"]},
                        {"label": "Fördermittelgeber Freitext", "value": ds["funding_funder_free"]},
                        {"label": "Programm / Förderlinie", "value": ds["funding_program"]}
                    ]
                },
                {
                    "group_name": "4 - Bewilligte Mittel & Ressourcen",
                    "fields": [
                        {"label": "Bewilligte Fördersumme", "value": f"{ds['amount_granted']} {ds['amount_currency']}"},
                        {"label": "Erhaltene Fördersumme", "value": ds["amount_received"]},
                        {"label": "SAP-Finanzstelle / Innenauftrag", "value": ds["sap_internal_id"]},
                        {"label": "Bewilligte FDM-Mittel", "value": ds["res_research_data"]},
                        {"label": "Bewilligte Publikationskosten", "value": ds["res_pub_costs"]},
                        {"label": "davon Open Access Kosten", "value": ds["res_openaccess"]},
                        {"label": "Bewilligte Projektpauschale", "value": ds["res_overhead"]},
                        {"label": "Eigenanteil Universität Vechta", "value": ds["funding_contrib_vec"]},
                        {"label": "Zeitaufschreibung / SAP-Nr.", "value": ds["typevec_contribution"]},
                        {"label": "DAAD Personen", "value": ds["daad_persons"]}
                    ]
                },
                {
                    "group_name": "5 - Kennzeichen & Identifikatoren",
                    "fields": [
                        {"label": "Förderkennzeichen", "value": ds["funding_identifier"]},
                        {"label": "DFG-Geschäftszeichen", "value": ds["dfg_geschaeftszeichen"]},
                        {"label": "DFG-Projektnummer", "value": ds["dfg_projektnummer"]}
                    ]
                },
                {
                    "group_name": "6 - Open Access & Compliance",
                    "fields": [
                        {"label": "Open Access-Regelung", "value": ds["oa_mandate"]},
                        {"label": "URL der OA-Policy", "value": ds["oa_mandate_url"]},
                        {"label": "Embargo gilt bis", "value": ds["embargo_lift"]}
                    ]
                }
            ]
        else:
            # === СТРУКТУРА PDF ДЛЯ APPLICATION (Стандартная) ===
            if app_type == "FACULTY_1":
                faculty_label = "Fakultät I"
                faculty_value = ds["fak_i_unit"] or ds["org_unit"]
            elif app_type == "FACULTY_2":
                faculty_label = "Fakultät II"
                faculty_value = ds["org_unit"]
            else:
                faculty_label = "Zentrale Einrichtung / Sonstige (OZ)"
                faculty_value = ds["org_unit"]

            return [
                {
                    "group_name": "0 - Typ der Antragsanmeldung",
                    "fields": [
                        {"label": "Kategorie / Typ", "value": ds["app_type_display"]},
                        {"label": "Federführende OE", "value": ds["federfuehrende_oe"]},
                        {"label": "Aktenplanzeichen", "value": ds["aktenplanzeichen"]}
                    ]
                },
                {
                    "group_name": "1 - Allgemeine Informationen",
                    "fields": [
                        {"label": "Projektbezeichnung/Titel", "value": ds["title"]},
                        {"label": "Akronym", "value": ds["acronym"]},
                        {"label": "Projektform", "value": ds["project_type"]},
                        {"label": "Projektzweck", "value": ds["project_purpose"]},
                        {"label": "(Geplanter) Projektstart/ Start der Förderung", "value": ds["funding_start"]},
                        {"label": "(Geplantes) Projektende/ Ende der Förderung", "value": ds["funding_end"]}
                    ]
                },
                {
                    "group_name": "2 - Organisatorische Informationen",
                    "fields": [
                        {"label": faculty_label, "value": faculty_value},
                        {"label": "Zuordnung zur Organisationseinheit", "value": ds["org_unit"]},
                        {"label": "Institut", "value": ds["institut"]},
                        {"label": "Wissenschaftliche Projektleitung", "value": ds["investigator"]},
                        {"label": "(Weitere) Ansprechperson", "value": ds["contact_person"]},
                        {"label": "E-Mail Kontaktadresse", "value": ds["contact_email"]},
                        {"label": "Kooperationsinstitutionen im Haus (intern)", "value": ds["cooperation_org_unit"]},
                        {"label": "Kooperierende Institute", "value": ds["institute_alt"]},
                        {"label": "Kooperationspartner*innen im Haus (intern)", "value": ds["cooperation_person"]},
                        {"label": "weitere antragstellende Institutionen oder Kooperationspartner (extern)",
                         "value": ds["cooperation_extern"]},
                        {"label": "Koordination bei Verbundprojekten", "value": ds["lead"]},
                        {"label": "Name koordinierende Einrichtung bei Verbundprojekten",
                         "value": ds["inst_name_lead"]},
                        {"label": "FDM Beratung", "value": ds["consulting_researchdata"]}
                    ]
                },
                {
                    "group_name": "3 - Inhaltliche Beschreibung",
                    "fields": [
                        {"label": "Forschungsschwerpunkt", "value": ds["research_subject"]},
                        {"label": "Querschnittsthema", "value": ds["crosssection_subject"]},
                        {"label": "Anderer Schwerpunkt/ weiteres Thema oder Fachgebiet", "value": ds["subject_other"]},
                        {"label": "Projektbeschreibung", "value": ds["abstract"]},
                        {"label": "Erhebung personen- или gesundheitsbezogene Daten",
                         "value": ds["personell_health_data"]}
                    ]
                },
                {
                    "group_name": "4 - Informationen zur Beantragung",
                    "fields": [
                        {"label": "Typ/Art der Förderung", "value": ds["funding_type"]},
                        {"label": "Fördermittelgeber", "value": ds["funding_funder"]},
                        {"label": "Fördermittelgeber Freitext", "value": ds["funding_funder_free"]},
                        {"label": "Programm/Förderlinie", "value": ds["funding_program"]},
                        {"label": "Ende der Einreichungsfrist", "value": ds["stage_deadline"]}
                    ]
                },
                {
                    "group_name": "5 - Budgetplan",
                    "fields": [
                        {"label": "Beantragte Personalmittel", "value": ds["resources_staff"]},
                        {"label": "Erläuterungen zum geplanten Personal", "value": ds["hr_explained"]},
                        {"label": "Beantragte Sachmittel", "value": ds["resources_material"]},
                        {"label": "davon beantragte Kosten für Unteraufträge", "value": ds["resources_subcontracting"]},
                        {"label": "davon beantragte FDM-Mittel", "value": ds["resources_research_data"]},
                        {"label": "davon beantragte Publikationskosten", "value": ds["resources_pub_costs"]},
                        {"label": "davon beantragte Open Access Kosten", "value": ds["resources_openaccess"]},
                        {"label": "Beantragte Projektpauschale", "value": ds["resources_overhead"]},
                        {"label": "Antragssumme", "value": ds["funding_amount"]},
                        {"label": "Einzubringender Eigenanteil der Universität Vechta",
                         "value": ds["funding_contrib_vec"]},
                        {"label": "Eigenanteil Haushaltspersonal durch Zeitaufschreibung",
                         "value": ds["hr_resources_vec"]},
                        {"label": "Eigenleistung durch Haushaltsmittel mit entsprechender SAP-Nr.",
                         "value": ds["resources_contrib_vec"]},
                        {"label": "Eigenleistung durch komplementäre Drittmittel mit entsprechender SAP-Nr.",
                         "value": ds["complementary_resources"]},
                        {"label": "DAAD Personen", "value": ds["daad"]},
                        {"label": "Ergebnisse der Forschung / Auflagen für Forschungsergebnisse",
                         "value": ds["research_results"]},
                        {"label": "Projektauflagen", "value": ds["project_requirements"]},
                        {"label": "Erläuterungen der Auflagen", "value": ds["explication_requirements"]},
                        {"label": "Kapazitäre Auswirkungen", "value": ds["capacities"]},
                        {"label": "Erläuterung der Lehrbeeinflussung", "value": ds["capacities_explanation"]},
                        {"label": "Benötigte Arbeitsplätze bei Genehmigung", "value": ds["facilities"]},
                        {"label": "Rechtsverbindliche Unterschrift", "value": ds["firmation"]},
                        {"label": "Einverständnis Datenverarbeitung", "value": ds["consent_data"]}
                    ]
                },
                {
                    "group_name": "6 - Status der Antragsanmeldung",
                    "fields": [
                        {"label": "Antragsstatus", "value": ds["vero_status"]}
                    ]
                }
            ]
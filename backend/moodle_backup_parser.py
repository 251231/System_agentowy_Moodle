import os
import shutil
import uuid
import lxml.etree as ET
from pathlib import Path

class MoodleXMLModifier:
    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.backup_xml_path = workspace / "moodle_backup.xml"

    def inject_h5p_generated(self):
        """
        Znajduje wszystkie paczki H5P w `h5p_generated`,
        tworzy dla nich strukture activities/ w formacie Moodle i
        modyfikuje główny plik moodle_backup.xml.
        """
        h5p_dir = self.workspace / "h5p_generated"
        if not h5p_dir.exists():
            return
            
        # Sprawdzamy czy istnieje moodle_backup.xml
        if not self.backup_xml_path.exists():
            print("[MoodleXMLModifier] Brak moodle_backup.xml!")
            return

        parser = ET.XMLParser(remove_blank_text=False)
        tree = ET.parse(str(self.backup_xml_path), parser)
        root = tree.getroot()

        activities_node = root.find(".//activities")
        if activities_node is None:
            # Tworzymy wezel jesli nie istnieje (bardzo rzadkie)
            contents = root.find(".//contents")
            if contents is not None:
                activities_node = ET.SubElement(contents, "activities")

        # Szukamy wolnego/najwyzszego moduleid (heuristyka)
        highest_id = 999000
        for act in activities_node.findall("activity"):
            mid = act.findtext("moduleid")
            if mid and mid.isdigit():
                highest_id = max(highest_id, int(mid))

        for item in h5p_dir.iterdir():
            if item.is_dir() and (item / "h5p.json").exists():
                highest_id += 1
                module_id = str(highest_id)
                self._create_activity_descriptor(item, module_id)
                self._append_to_backup_xml(activities_node, item, module_id)

        # Zapis modyfikacji
        tree.write(str(self.backup_xml_path), encoding="utf-8", xml_declaration=True)

    def _create_activity_descriptor(self, h5p_source: Path, module_id: str):
        """
        Tworzy katalog np. activities/h5pactivity_999001/ i generuje pliki.
        W normalnym Moodle'u pliki .h5p trafialyby do files.xml + puli hashy SHA1, 
        jednak tutaj (jako proxy) zastosujemy folder pluginowy i osadzony content, 
        lub prosta strukture XML pluginu.
        """
        dest = self.workspace / "activities" / f"h5pactivity_{module_id}"
        dest.mkdir(parents=True, exist_ok=True)
        
        # Przenoszenie wygenerowanych plikow (Moodle docelowo przyjmie je z zewnatrz lub w inforef)
        # Aby to po prostu zadzialalo jako dowod koncepcji, uzywamy osadzonej struktury H5P
        target_content = dest / "h5p_content"
        shutil.move(str(h5p_source), str(target_content))

        # module.xml
        module_xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<module id="{module_id}" version="2023042400">
  <modulename>h5pactivity</modulename>
  <title>Fiszki edukacyjne (AI)</title>
  <description></description>
  <visible>1</visible>
  <visibleoncoursepage>1</visibleoncoursepage>
</module>'''
        (dest / "module.xml").write_text(module_xml, encoding="utf-8")

        # inforef.xml (puste powiazania)
        inforef_xml = '''<?xml version="1.0" encoding="UTF-8"?>\n<inforef></inforef>'''
        (dest / "inforef.xml").write_text(inforef_xml, encoding="utf-8")

        # h5pactivity.xml (minimalny tag rekordu)
        h5p_xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<activity id="{module_id}" moduleid="{module_id}" modulename="h5pactivity" contextid="1">
  <h5pactivity id="{module_id}">
    <name>Fiszki edukacyjne (AI)</name>
    <timecreated>{self._get_timestamp()}</timecreated>
    <timemodified>{self._get_timestamp()}</timemodified>
    <displayoptions>0</displayoptions>
  </h5pactivity>
</activity>'''
        (dest / "h5pactivity.xml").write_text(h5p_xml, encoding="utf-8")

    def _append_to_backup_xml(self, activities_node: ET.Element, h5p_source: Path, module_id: str):
        # <activity>
        #   <moduleid>999001</moduleid>
        #   <sectionid>1</sectionid> <!-- Dodajemy do 1 sekcji zeby sie gdzies wyswietlilo -->
        #   <modulename>h5pactivity</modulename>
        #   <title>Fiszki edukacyjne (AI)</title>
        #   <directory>activities/h5pactivity_999001</directory>
        # </activity>
        act = ET.SubElement(activities_node, "activity")
        ET.SubElement(act, "moduleid").text = module_id
        ET.SubElement(act, "sectionid").text = "1" 
        ET.SubElement(act, "modulename").text = "h5pactivity"
        ET.SubElement(act, "title").text = "Fiszki edukacyjne (AI)"
        ET.SubElement(act, "directory").text = f"activities/h5pactivity_{module_id}"
        
    def _get_timestamp(self):
        import time
        return str(int(time.time()))

# Catálogo territorial de México

La app usa el Catálogo Único de Claves de Áreas Geoestadísticas Estatales, Municipales y Localidades del INEGI. El corte municipal de junio de 2026 contiene 2,478 áreas geoestadísticas municipales, incluidas las 16 alcaldías de Ciudad de México. Las 32 entidades de este corte coinciden, clave y nombre, con el catálogo nacional de entidades. Las fechas corresponden al corte de la información. Consulta realizada el 22 de noviembre de 2026. [Consulta del catálogo](https://www.inegi.org.mx/app/ageeml/) · [Historial de cortes municipales](https://www.inegi.org.mx/app/api/cateml/catuniAPI/ObtenerFecCorMun/)

| Descarga nacional | CSV UTF-8 del corte | SHA-256 del CSV |
| --- | --- | --- |
| [Entidades](https://www.inegi.org.mx/contenidos/app/ageeml/catun_entidad.zip) | `AGEEML_202512121056362_utf.csv` | `b9eaa950065ebce01e4216719fefa9bb122eef87701d493426dd898e8af26708` |
| [Municipios y alcaldías](https://www.inegi.org.mx/contenidos/app/ageeml/catun_municipio.zip) | `AGEEML_20268211656753_utf8.csv` | `2f2d08c8a13b037203b8fd6822983d242f79cf787b904a1f9df101635f557387` |

La clave del documento y el campo `clave` conservan el texto de `CVEGEO`, incluidos los ceros iniciales. El nombre procede de `NOM_ENT` o `NOM_MUN`. Cada municipio enlaza con su entidad mediante `CVE_ENT`. Los fixtures se distribuyen con la app y se cargan por orden de archivo, primero las entidades.

El 22 de noviembre de 2026 se cotejaron las 32 respuestas municipales del servicio web del INEGI (`mgem/{cve_ent}`). Sus 2,478 ternas de clave, nombre y entidad coinciden con el archivo de municipios. [Servicio web del INEGI](https://www.inegi.org.mx/servicios/catalogounico/)

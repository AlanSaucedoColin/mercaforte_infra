# Catálogo territorial de Morelos

La app distribuye Morelos (clave de entidad `17`) y sus 36 municipios (claves `17001` a `17036`). Los registros proceden del corte municipal de junio de 2026 del Catálogo Único de Claves de Áreas Geoestadísticas Estatales, Municipales y Localidades del INEGI. [Consulta del catálogo](https://www.inegi.org.mx/app/ageeml/) · [Historial de cortes municipales](https://www.inegi.org.mx/app/api/cateml/catuniAPI/ObtenerFecCorMun/)

| Descarga nacional | CSV UTF-8 del corte | SHA-256 del CSV |
| --- | --- | --- |
| [Entidades](https://www.inegi.org.mx/contenidos/app/ageeml/catun_entidad.zip) | `AGEEML_202512121056362_utf.csv` | `b9eaa950065ebce01e4216719fefa9bb122eef87701d493426dd898e8af26708` |
| [Municipios y alcaldías](https://www.inegi.org.mx/contenidos/app/ageeml/catun_municipio.zip) | `AGEEML_20268211656753_utf8.csv` | `2f2d08c8a13b037203b8fd6822983d242f79cf787b904a1f9df101635f557387` |

La clave del documento y el campo `clave` conservan el texto de `CVEGEO`, incluidos los ceros iniciales. El nombre procede de `NOM_ENT` o `NOM_MUN`. Cada municipio enlaza con su entidad mediante `CVE_ENT`. Los fixtures se distribuyen con la app y se cargan por orden de archivo, primero las entidades.

El 25 de noviembre de 2026 se verificó que las 36 claves y nombres de Morelos coinciden con la respuesta municipal del servicio web del INEGI. [Municipios de Morelos](https://gaia.inegi.org.mx/wscatgeo/v2/mgem/17)

Para centrar el mapa sin un marcador guardado, la app incluye las coordenadas de cada cabecera municipal. Se obtuvieron uniendo la clave municipal y `cve_cab` para consultar la localidad correspondiente en el mismo servicio del INEGI. [Municipios y claves de cabecera](https://gaia.inegi.org.mx/wscatgeo/v2/mgem/17) · [Localidad de Cuernavaca](https://gaia.inegi.org.mx/wscatgeo/v2/localidades/170070001)

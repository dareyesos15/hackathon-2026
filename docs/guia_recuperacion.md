# Guía del módulo de recuperación · casos de ejemplo

Para el personal que opera la recuperación después del sismo: UGR, Cuerpo Oficial de Bomberos,
Secretaría de Desarrollo Social, Cruz Roja y entidades de servicios. Explica el flujo con seis
casos de ejemplo que se cargan en minutos y se revisan en pantalla.

> **Use los casos de ejemplo solo en un entorno de capacitación.** Llevan números reservados
> (formatos 990001–990006, actas 990101–990105, planilla 990201) y documentos ficticios. En el
> entorno de operación real no se cargan: los registros de Dacora no se borran (son solo-agregar,
> para que quede trazabilidad).

## 1. El flujo en una línea

**Revisión a predio** (formato GUE-RPD-FR-02) → **semáforo** de habitabilidad → **censo único**
(RUD) → **actas de entrega** (kit, subsidio de arriendo, cupo en albergue) → **visitas de
entidades** → **necesidades** en el tablero.

Cada paso alimenta el siguiente: lo que se escribe una vez no se vuelve a escribir.

| Pestaña | Para qué | Quién la usa |
|---|---|---|
| Habitabilidad | Transcribir o llenar en terreno el formato de revisión a predio; ver las visitas pendientes de cada entidad | Bomberos, inspectores, UGR |
| Censo único | Completar la planilla del RUD del hogar; inscribirlo en el RUD; exportar el CSV | Desarrollo Social, UGR |
| Ayudas | Registrar cada acta de entrega: kits, subsidio de arriendo, cupo en albergue y salida | Cruz Roja, Desarrollo Social |
| Albergues | Ver ocupación, cupos libres, entidad administradora y servicios | Administración del albergue |
| Tablero | Lo que se necesita hoy y los 10 indicadores para el COE | PMU, COE |

## 2. Reglas que el sistema hace cumplir

- **Un predio es un predio.** Código catastral o manzana + dirección: las visitas repetidas se
  suman al mismo predio (no cuentan doble).
- **Un hogar es un hogar.** Se reconoce por el documento del jefe de hogar, del que Dacora guarda
  solo una huella cifrada. Registrar el mismo hogar de nuevo completa sus datos, no lo duplica.
- **Un papel se registra una vez.** El N.º del formato, de la planilla o del acta no se acepta
  dos veces.
- **Semáforo coherente.** Si se recomienda evacuar, el predio queda en rojo; sin afectación queda
  en verde; con afectación total, en rojo.
- **Sin doble beneficio.** La misma ayuda al mismo hogar dentro de su periodo se bloquea; solo se
  entrega con una justificación, que queda marcada.
- **Albergue con cupo.** El cupo exige elegir el albergue, solo si está abierto y tiene espacio
  para todo el hogar; la ocupación sube y baja sola con las entradas y salidas.
- **Habeas Data (Ley 1581).** Nombres, teléfonos, cédulas, fechas de nacimiento y firmas
  **quedan solo en el papel**. En Dacora: conteos y huellas cifradas.

## 3. Cargar los casos de ejemplo

Con la demo en marcha (`docker compose up -d`):

```bash
docker compose exec api python scripts/seed_recovery_example.py
```

Tarda unos segundos e imprime qué pasó en cada paso. Si ya estaban cargados, no hace nada.
Entre a <http://localhost:8080/recuperacion/> con el usuario `coe` (contraseña de demo en
`.env.example`).

## 4. Los seis casos

### Caso 1 · Milán · Edificio con grietas y evacuación: familia al albergue

- **Formato 990001**: afectación parcial, se recomienda evacuar, requiere visita de UGR y CHEC.
- **Qué hace Dacora:** semáforo **rojo** (daño mayor) aunque la afectación sea parcial, porque se
  evacuó; crea el hogar en el censo (5 personas, prioridad por niñez y adulto mayor); abre dos
  visitas pendientes.
- **Actas:** 990101 cupo en el Coliseo Mayor (la ocupación sube en 5 personas y 1 mascota) y
  990102 kit alimentario.
- **La UGR ya hizo su visita**; la CHEC sigue pendiente.
- **Revise:** Habitabilidad → *Visitas de entidades pendientes* (solo CHEC del caso 1);
  Albergues → Coliseo Mayor 5 personas, 1 hogar; Censo → hogar *En albergue*.

### Caso 2 · Centro · Casa colapsada de arrendatarios: subsidio de arriendo

- **Formato 990002**: afectación total, colapso, arrendatarios (el documento del propietario se
  guarda solo como huella), requiere Obras Públicas e Inspección de Policía.
- **Censo:** la planilla 990201 completa el mismo hogar (tenencia, edades, mujeres, pérdidas)
  sin duplicarlo; queda **inscrito en el RUD**. Estado de la vivienda: **destruida**.
- **Acta 990103:** subsidio de arriendo de $550.000 mensuales × 3 meses.
- **Revise:** Censo → hogar *En arriendo temporal*, *Inscrito en RUD*; Exportar CSV → fila con
  planilla 990201.

### Caso 3 · San José · Daño moderado: uso restringido, la familia se queda

- **Formato 990003**: afectación parcial, sin evacuación, requiere Aguas de Manizales.
- **Qué hace Dacora:** semáforo **amarillo** (uso restringido); el hogar sigue *En su vivienda*.
- **Acta 990104:** kit de aseo y cocina.

### Caso 4 · Palermo · Predio sin daño

- **Formato 990004**: sin afectación → semáforo **verde**.
- No se anotó documento del encuestado: el predio cuenta como evaluado, pero el hogar no entra al
  censo (el sistema lo advierte al registrar).

### Caso 5 · Los Agustinos · Familia vulnerable evacuada sin solución de vivienda

- **Formato 990005**: sismo y deslizamiento, afectación total, evacuación, dos adultos mayores y
  una persona con discapacidad; requiere Corpocaldas y UGR. El notificado **no firmó**.
- **Qué hace Dacora:** semáforo rojo; el hogar queda **sin albergue ni arriendo**.
- **Revise:** Tablero → *Lo que se necesita hoy*: **Familias en predio rojo sin solución de
  vivienda** (crítica) y **Hogares con niñez, adultos mayores, discapacidad o gestación sin
  ayuda**. Esto es lo que se atiende primero.
- **Para cerrarlo en la capacitación:** en Ayudas, registre un cupo en albergue para ese hogar
  (documento `1111100005`) y vea desaparecer la necesidad del tablero.

### Caso 6 · Milán · Segunda visita y entrega repetida

- **Formato 990006**: el mismo apartamento del caso 1, días después; ahora afectación total.
- **Qué hace Dacora:** se une al mismo predio (**visita n.º 2**) y al mismo hogar; como la
  familia ya está en el Coliseo Mayor, **no repite** la ruta de la Cruz Roja.
- **Acta 990105:** un segundo kit alimentario dentro del periodo se **bloquea**; se entrega solo
  con justificación y queda marcado como repetido.
- **Revise:** Habitabilidad → predio del caso 1 con 2 visitas y sus dos formatos; Ayudas →
  *1 repetidas con justificación*.

## 5. Lo que muestra el tablero con los casos

| Indicador | Valor esperado | Por qué |
|---|---|---|
| Familias damnificadas únicas | 4 | Los casos 1 y 6 son el mismo hogar; el caso 4 no tiene documento |
| Predios evaluados únicos | 5 | Seis formatos, pero el caso 6 es el mismo predio del caso 1 |
| Visitas repetidas unidas a su predio | 1 | El caso 6 |
| Semáforo | 1 verde, 1 amarillo, 2 rojos, 1 colapsado | Casos 4, 3, 1 y 5, y 2 |
| Familias por situación | 1 en albergue, 1 en arriendo, 1 en casa, 1 sin solución | Casos 1, 2, 3 y 5 |
| Visitas de entidades pendientes | 6 | Todas las derivaciones menos la de la UGR del caso 1 |

## 6. Pasar a la operación real

1. Use un entorno sin los casos de ejemplo.
2. Cargue los albergues reales y su entidad administradora (pestaña Albergues → *Administrar*).
3. Entregue a las cuadrillas el formato GUE-RPD-FR-02 en papel; la transcripción usa el mismo
   orden de secciones.
4. Defina quién marca cada visita de entidad (usuario de agencia) y quién inscribe en el RUD.
5. Exporte el CSV del RUD con la cadencia que pida la UNGRD.

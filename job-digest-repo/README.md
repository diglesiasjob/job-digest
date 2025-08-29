# Weekly Job Digest (Zona Oeste Comunidad de Madrid)

Script y workflow de GitHub Actions para generar **un informe semanal** de ofertas de trabajo a partir de **feeds RSS** (InfoJobs, Empléate/SEPE, etc.), aplicando filtros por **sector** y **municipios** de la **zona oeste de la Comunidad de Madrid**, enviándolo por **email** y guardando una versión **HTML/TXT**.

## Estructura
```
job-digest-repo/
├─ job_digest.py
├─ config.example.yaml
├─ requirements.txt
├─ .gitignore
├─ LICENSE
└─ .github/workflows/weekly-job-digest.yml
```

## Configuración rápida

1. Copia `config.example.yaml` a `config.yaml` y edítalo:
   - `to_email` / `from_email` → tu correo.
   - `feeds` → pega las **URLs RSS** de tus búsquedas (una por línea).
   - `include_keywords` → palabras clave del **sector** (p. ej. "marketing", "data", etc.).
   - `include_locations` → municipios (p. ej. "Pozuelo", "Majadahonda", "Las Rozas"…).
   - `exclude_keywords` → términos a **excluir** (p. ej. "prácticas", "junior").
   - `lookback_days` → días hacia atrás (7 = semanal).

2. Prepara variables de entorno para SMTP (si ejecutas local):
   ```bash
   export SMTP_HOST=smtp.gmail.com
   export SMTP_PORT=587
   export SMTP_USER=tu_email@ejemplo.com
   export SMTP_PASS=tu_app_password_o_contraseña
   export SMTP_STARTTLS=1
   ```

3. Instala dependencias y ejecuta localmente:
   ```bash
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   python job_digest.py --config config.yaml
   ```

## Automatización con GitHub Actions

1. Sube este repo a GitHub.
2. En el repo → **Settings → Secrets and variables → Actions**, crea estos **Secrets**:
   - `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `SMTP_STARTTLS`
3. El workflow `weekly-job-digest.yml` está programado cada **lunes 08:00 (Europa/Madrid)**. Puedes ejecutarlo manualmente con **Run workflow**.

> Los artefactos `digest.html` y `digest.txt` se guardan en el job; además, si `to_email` está configurado en `config.yaml`, se envía el email.

## RSS: ejemplos
- Crea tu búsqueda en el portal (InfoJobs, Empléate/SEPE, etc.), filtra por provincia/municipio/sector y copia el **feed RSS** de esa búsqueda.
- Añade tantas URLs como necesites en la clave `feeds`.

## Personalización
- Ajusta el cron en `.github/workflows/weekly-job-digest.yml` si prefieres otro día/hora.
- Amplía `include_locations` o añade más `feeds` para cubrir otros municipios o radios.

---

**Licencia:** MIT

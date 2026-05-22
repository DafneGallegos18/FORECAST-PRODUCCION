"""
Servicio de envío de correos electrónicos via SMTP.
Utiliza la librería estándar de Python (smtplib + email).
Las plantillas HTML se renderizan con Jinja2.
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional
from jinja2 import Template

from config.settings import smtp_settings


# ── Plantilla HTML base para correos ───────────────────────────────

FORECAST_EMAIL_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: 'Segoe UI', Arial, sans-serif; background: #f5f5f5; padding: 20px; }
        .container { max-width: 600px; margin: 0 auto; background: white; border-radius: 8px;
                     box-shadow: 0 2px 8px rgba(0,0,0,0.1); overflow: hidden; }
        .header { background: linear-gradient(135deg, #1a237e, #283593); color: white; padding: 24px; }
        .header h1 { margin: 0; font-size: 20px; }
        .header p { margin: 4px 0 0; opacity: 0.8; font-size: 14px; }
        .body { padding: 24px; }
        .stat-row { display: flex; gap: 12px; margin-bottom: 16px; }
        .stat-box { flex: 1; background: #f8f9fa; border-radius: 6px; padding: 12px; text-align: center; }
        .stat-box .number { font-size: 24px; font-weight: bold; color: #1a237e; }
        .stat-box .label { font-size: 12px; color: #666; }
        .alerts { margin: 16px 0; }
        .alert-item { padding: 8px 12px; border-left: 3px solid #ff5722; background: #fff3e0;
                      margin-bottom: 4px; border-radius: 0 4px 4px 0; font-size: 13px; }
        .btn { display: inline-block; background: #1a237e; color: white; padding: 12px 24px;
               text-decoration: none; border-radius: 6px; font-weight: bold; margin-top: 16px; }
        .footer { padding: 16px 24px; background: #f8f9fa; font-size: 12px; color: #999; text-align: center; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 Forecast de Producción</h1>
            <p>Semana del {{ fecha }}</p>
        </div>
        <div class="body">
            <div class="stat-row">
                <div class="stat-box">
                    <div class="number">{{ total_productos }}</div>
                    <div class="label">Productos</div>
                </div>
                <div class="stat-box">
                    <div class="number">{{ total_alertas }}</div>
                    <div class="label">Alertas</div>
                </div>
                <div class="stat-box">
                    <div class="number">{{ estado }}</div>
                    <div class="label">Estado</div>
                </div>
            </div>

            {% if alertas %}
            <div class="alerts">
                <strong>⚠️ Alertas Activas:</strong>
                {% for alerta in alertas[:5] %}
                <div class="alert-item">{{ alerta }}</div>
                {% endfor %}
                {% if alertas | length > 5 %}
                <div style="font-size: 12px; color: #999; margin-top: 8px;">
                    ... y {{ alertas | length - 5 }} alertas más
                </div>
                {% endif %}
            </div>
            {% endif %}

            <p>El forecast semanal está listo para revisión. Haz clic en el botón para ver los detalles completos, realizar ajustes y aprobar el envío.</p>

            <a href="{{ link }}" class="btn">Ver Forecast Completo →</a>
        </div>
        <div class="footer">
            Generado automáticamente por el Sistema de Forecast de Producción
        </div>
    </div>
</body>
</html>
"""


def send_email(
    to: List[str],
    subject: str,
    html_body: str,
    cc: Optional[List[str]] = None,
) -> bool:
    """
    Envía un correo electrónico via SMTP.

    Args:
        to: Lista de destinatarios.
        subject: Asunto del correo.
        html_body: Cuerpo del correo en HTML.
        cc: Lista opcional de destinatarios en copia.

    Returns:
        True si el envío fue exitoso.
    """
    if not smtp_settings.host:
        print("⚠️  SMTP no configurado. Correo NO enviado.")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{smtp_settings.from_name} <{smtp_settings.from_email}>"
    msg["To"] = ", ".join(to)
    if cc:
        msg["Cc"] = ", ".join(cc)

    msg.attach(MIMEText(html_body, "html"))

    all_recipients = to + (cc or [])

    try:
        with smtplib.SMTP(smtp_settings.host, smtp_settings.port) as server:
            server.starttls()
            server.login(smtp_settings.user, smtp_settings.password)
            server.sendmail(smtp_settings.from_email, all_recipients, msg.as_string())

        print(f"✅ Correo enviado a {len(all_recipients)} destinatario(s)")
        return True

    except Exception as e:
        print(f"❌ Error al enviar correo: {e}")
        return False


def send_forecast_notification(
    to: List[str],
    fecha: str,
    total_productos: int,
    total_alertas: int,
    estado: str,
    alertas: List[str],
    link: str,
    cc: Optional[List[str]] = None,
) -> bool:
    """
    Envía la notificación semanal del forecast con la plantilla HTML.

    Args:
        to: Lista de destinatarios.
        fecha: Fecha de la semana del forecast.
        total_productos: Número de productos en el forecast.
        total_alertas: Número de alertas activas.
        estado: Estado del forecast (Borrador, Aprobado, etc.).
        alertas: Lista de mensajes de alerta para mostrar.
        link: URL del portal web para ver el forecast.
        cc: Destinatarios en copia.

    Returns:
        True si el envío fue exitoso.
    """
    template = Template(FORECAST_EMAIL_TEMPLATE)
    html = template.render(
        fecha=fecha,
        total_productos=total_productos,
        total_alertas=total_alertas,
        estado=estado,
        alertas=alertas,
        link=link,
    )

    subject = f"📊 Forecast de Producción — Semana del {fecha}"
    return send_email(to, subject, html, cc)

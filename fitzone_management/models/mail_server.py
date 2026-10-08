from odoo import models


class IrMailServer(models.Model):
    _inherit = 'ir.mail_server'

    def _build_email__(
        self,
        email_from,
        email_to,
        subject,
        body,
        email_cc=None,
        email_bcc=None,
        reply_to=False,
        attachments=None,
        message_id=None,
        references=None,
        object_id=False,
        subtype='plain',
        headers=None,
        body_alternative=None,
        subtype_alternative='plain',
    ):
        normal_attachments = []
        inline_attachments = []

        for attachment in attachments or []:
            if len(attachment) != 3:
                normal_attachments.append(attachment)
                continue

            fname, fcontent, mime = attachment

            if fname.startswith('__fitzone_inline_barcode__'):
                inline_attachments.append(
                    (fname, fcontent, mime)
                )
            else:
                normal_attachments.append(attachment)

        message = super()._build_email__(
            email_from=email_from,
            email_to=email_to,
            subject=subject,
            body=body,
            email_cc=email_cc,
            email_bcc=email_bcc,
            reply_to=reply_to,
            attachments=normal_attachments,
            message_id=message_id,
            references=references,
            object_id=object_id,
            subtype=subtype,
            headers=headers,
            body_alternative=body_alternative,
            subtype_alternative=subtype_alternative,
        )

        if not inline_attachments:
            return message

        html_part = None

        for part in message.walk():
            if part.get_content_type() == 'text/html':
                html_part = part
                break

        if not html_part:
            return message

        for fname, fcontent, mime in inline_attachments:
            barcode_id = fname.replace(
                '__fitzone_inline_barcode__',
                ''
            ).rsplit('.', 1)[0]

            cid = f'fitzone_barcode_{barcode_id}'

            maintype, subtype_name = (
                mime.split('/', 1)
                if mime and '/' in mime
                else ('application', 'octet-stream')
            )

            html_part.add_related(
                fcontent,
                maintype=maintype,
                subtype=subtype_name,
                cid=cid,
                filename='fitzone_barcode.png',
            )

            related_part = html_part.get_payload()[-1]

            if related_part.get('Content-Disposition'):
                related_part.replace_header(
                    'Content-Disposition',
                    'inline; filename="fitzone_barcode.png"',
                )
            else:
                related_part['Content-Disposition'] = (
                    'inline; filename="fitzone_barcode.png"'
                )

        return message

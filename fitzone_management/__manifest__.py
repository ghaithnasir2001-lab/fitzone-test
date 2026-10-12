{
    'name': 'FitZone Management',
    'version': '19.0.1.0.0',
    'category': 'Services',
    'summary': 'FitZone gym management system',
    'description': """
        FitZone gym management system.
    """,
    'depends': [
        'base',
        'product',
        'hr',
        'mail',
        'account',
    ],
    'data': [
        'security/fitzone_groups.xml',
        'security/fitzone_security.xml',
        'security/ir.model.access.csv',

        'data/health_sequence.xml',
        'data/membership_sequence.xml',
        'data/checkin_sequence.xml',
        'data/membership_cron.xml',
        'data/injury_rehab_sequence.xml',
        'data/membership_email_template.xml',
        'data/payment_sequence.xml',

        'views/membership_package_views.xml',
        'views/membership_subscription_views.xml',
        'views/membership_freeze_views.xml',
        'views/checkin_views.xml',
        'views/membership_payment_views.xml',

        'views/facility_views.xml',
        'views/class_views.xml',
        'views/class_schedule_views.xml',
        'views/swimming_slot_views.xml',
        'views/hr_employee_views.xml',
        'views/booking_views.xml',
        'report/booking_details_report_templates.xml',
        'report/membership_details_report_templates.xml',
        'report/injury_rehab_report_templates.xml',
        'views/subscriber_views.xml',
        'views/health_views.xml',
        'views/injury_rehab_views.xml',
        'views/management_dashboard_views.xml',
        'views/trainer_views.xml',

        'data/booking_sequence.xml',
        'data/nutrition_sequence.xml',
        'views/nutrition_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'fitzone_management/static/src/js/checkin_barcode_scanner.js',
        ],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
    'author': 'FitZone Team',
}
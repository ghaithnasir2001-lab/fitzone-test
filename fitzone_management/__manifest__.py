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
        'account',
    ],
    'data': [
        'security/ir.model.access.csv',

        'data/health_sequence.xml',
        'data/membership_sequence.xml',
        'data/membership_cron.xml',
        'data/payment_sequence.xml',

        'views/membership_package_views.xml',
        'views/membership_subscription_views.xml',
        'views/membership_freeze_views.xml',
        'views/membership_payment_views.xml',

        'views/facility_views.xml',
        'views/class_views.xml',
        'views/class_schedule_views.xml',
        'views/swimming_slot_views.xml',
        'views/hr_employee_views.xml',
        'views/booking_views.xml',
        'views/subscriber_views.xml',
        'views/health_views.xml',
        'views/trainer_views.xml',


        'data/booking_sequence.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
    'author': 'FitZone Team',
}

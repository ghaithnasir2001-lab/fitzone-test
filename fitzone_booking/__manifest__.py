{
    'name': 'FitZone Booking',
    'version': '19.0.1.0.0',
    'category': 'Services',
    'summary': 'Classes and facilities management for FitZone',
    'description': """
        Manage FitZone facilities, classes, class schedules,
        and swimming slots.
    """,
    'depends': [
        'base',
        'product',
        'hr',
    ],
    'data': [
        'views/facility_views.xml',
        'views/class_views.xml',
        'views/class_schedule_views.xml',
        'views/swimming_slot_views.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
    'author': 'FitZone Team',
}
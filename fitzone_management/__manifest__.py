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
    ],
    'data': [
        'security/ir.model.access.csv',
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
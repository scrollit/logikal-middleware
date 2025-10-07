# -*- coding: utf-8 -*-
{
    'name': 'Logikal',
    'version': '18.0.1.9.1',
    'category': 'API',
    'summary': 'LOGIKAL API integration module for Logikal',
    'description': """
        LOGIKAL API Integration Module
        ============================
        
        This module provides comprehensive integration with the LOGIKAL API and Middleware.
        
        Features:
        ---------
        * Dual integration support: Direct API or Middleware
        * Authentication and session management
        * Configuration interface in Settings
        * Session logging for debugging and audit trail
        * Connection testing functionality
        * Error handling and logging
        * Automatic log cleanup
        * Project, phase, and elevation synchronization
        * Simplified navigation (no folder selection required with middleware)
        * Unified service layer for both integration modes
        * Sales Order integration with project import
        * Phase and elevation import as structured sales order lines
        
        Integration Modes:
        ------------------
        * Direct API: Traditional direct connection to Logikal API
        * Middleware: Modern integration via Logikal Middleware (recommended)
        .
    """,
    'author': 'Scrollit',
    'website': 'https://www.scrollit.be',
    'license': 'LGPL-3',
    'icon': '/logikal_api/static/description/icon.svg',
    'depends': [
        'base',
        'sale',
        'queue_job',
    ],
    'external_dependencies': {
        'python': ['requests'],
    },
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'security/record_rules.xml',
        'data/mbioe_import_config_data.xml',
        'views/mbioe_actions.xml',             # Phase 1: Define all actions first
        'views/mbioe_menus.xml',               # Phase 2: Define all menus (can reference actions)
        'views/mbioe_folder_views.xml',        # Phase 3: Define views (can reference menus)
        'views/mbioe_project_views.xml',
        'views/mbioe_phase_views.xml',
        'views/mbioe_elevation_views.xml',
        'views/mbioe_operations_views.xml',
        'views/mbioe_session_log_views.xml',
        'views/res_config_settings_views.xml',
        'views/mbioe_sync_views.xml',
        'views/sale_order_views.xml',
        'views/sale_order_line_views.xml',
        'views/mbioe_sales_integration_views.xml',
        'views/logikal_import_wizard_views.xml',
        # New middleware-based views
        'views/logikal_project_views.xml',
        'views/logikal_phase_views.xml',
        'views/logikal_elevation_views.xml',
        'views/logikal_menus.xml',
        'views/logikal_operations_views.xml',
    ],
    'demo': [
        # 'demo/demo.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}

"""Shared UI components for web routes."""


def get_base_layout(title: str, content: str, user: object = None, active_nav: str = "") -> str:
    """Get base HTML layout with navigation."""
    nav_items = [
        ("/", "Dashboard", "dashboard"),
        ("/workflows", "Workflows", "workflows"),
        ("/executions", "Execuções", "executions"),
    ]

    nav_html = ""
    for href, label, nav_id in nav_items:
        active_class = "bg-indigo-700 text-white" if nav_id == active_nav else "text-gray-300 hover:bg-indigo-700 hover:text-white"
        nav_html += f'<a href="{href}" class="px-3 py-2 rounded-md text-sm font-medium {active_class}">{label}</a>'

    user_section = ""
    if user:
        user_section = f"""
        <div class="flex items-center space-x-4">
            <span class="text-gray-300 text-sm">{user.email}</span>
            <button onclick="logout()" class="text-gray-300 hover:text-white text-sm font-medium">Sair</button>
        </div>
        """

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - Workflow Automation</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/htmx.org@1.9.12"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        /* Toast Notifications */
        .toast-container {{
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 9999;
            display: flex;
            flex-direction: column;
            gap: 10px;
        }}
        .toast {{
            background: white;
            border-radius: 8px;
            padding: 16px 20px;
            box-shadow: 0 10px 25px rgba(0,0,0,0.1);
            border-left: 4px solid;
            min-width: 300px;
            animation: slideIn 0.3s ease-out;
            display: flex;
            align-items: center;
            gap: 12px;
        }}
        .toast.success {{ border-left-color: #10b981; }}
        .toast.error {{ border-left-color: #ef4444; }}
        .toast.warning {{ border-left-color: #f59e0b; }}
        .toast.info {{ border-left-color: #3b82f6; }}

        @keyframes slideIn {{
            from {{
                transform: translateX(100%);
                opacity: 0;
            }}
            to {{
                transform: translateX(0);
                opacity: 1;
            }}
        }}
        @keyframes fadeOut {{
            from {{ opacity: 1; }}
            to {{ opacity: 0; }}
        }}
        .toast.hiding {{
            animation: fadeOut 0.3s ease-out forwards;
        }}

        /* Modal */
        .modal-overlay {{
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0,0,0,0.5);
            z-index: 1000;
            display: none;
            align-items: center;
            justify-content: center;
        }}
        .modal-overlay.active {{
            display: flex;
        }}
        .modal-content {{
            background: white;
            border-radius: 12px;
            max-width: 600px;
            width: 90%;
            max-height: 90vh;
            overflow-y: auto;
            animation: modalSlideIn 0.3s ease-out;
        }}
        @keyframes modalSlideIn {{
            from {{
                transform: scale(0.9);
                opacity: 0;
            }}
            to {{
                transform: scale(1);
                opacity: 1;
            }}
        }}

        /* Loading Spinner */
        .spinner {{
            border: 3px solid #f3f4f6;
            border-top: 3px solid #6366f1;
            border-radius: 50%;
            width: 24px;
            height: 24px;
            animation: spin 1s linear infinite;
        }}
        @keyframes spin {{
            0% {{ transform: rotate(0deg); }}
            100% {{ transform: rotate(360deg); }}
        }}

        /* Card Hover Effects */
        .workflow-card {{
            transition: all 0.2s ease;
        }}
        .workflow-card:hover {{
            transform: translateY(-2px);
            box-shadow: 0 10px 25px rgba(0,0,0,0.1);
        }}

        /* Status Badges */
        .badge {{
            display: inline-flex;
            align-items: center;
            padding: 4px 12px;
            border-radius: 9999px;
            font-size: 12px;
            font-weight: 500;
        }}
        .badge-success {{ background: #d1fae5; color: #065f46; }}
        .badge-warning {{ background: #fef3c7; color: #92400e; }}
        .badge-error {{ background: #fee2e2; color: #991b1b; }}
        .badge-neutral {{ background: #f3f4f6; color: #374151; }}
    </style>
</head>
<body class="bg-gray-50 min-h-screen">
    <!-- Navigation -->
    <nav class="bg-indigo-900 shadow-lg">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div class="flex justify-between h-16">
                <div class="flex items-center space-x-8">
                    <a href="/" class="text-xl font-bold text-white">
                        <i class="fas fa-cogs mr-2"></i>Workflow Automation
                    </a>
                    <div class="hidden md:flex items-center space-x-2">
                        {nav_html}
                    </div>
                </div>
                {user_section}
            </div>
        </div>
    </nav>

    <!-- Main Content -->
    {content}

    <!-- Toast Container -->
    <div id="toast-container" class="toast-container"></div>

    <!-- Global Scripts -->
    <script>
        // Toast Notification System
        function showToast(message, type = 'info', duration = 5000) {{
            const container = document.getElementById('toast-container');
            const toast = document.createElement('div');
            toast.className = `toast ${{type}}`;

            const icons = {{
                success: '<i class="fas fa-check-circle text-green-500 text-xl"></i>',
                error: '<i class="fas fa-exclamation-circle text-red-500 text-xl"></i>',
                warning: '<i class="fas fa-exclamation-triangle text-yellow-500 text-xl"></i>',
                info: '<i class="fas fa-info-circle text-blue-500 text-xl"></i>'
            }};

            toast.innerHTML = `
                ${{icons[type]}}
                <span class="text-gray-800 font-medium">${{message}}</span>
            `;

            container.appendChild(toast);

            setTimeout(() => {{
                toast.classList.add('hiding');
                setTimeout(() => toast.remove(), 300);
            }}, duration);
        }}

        // Modal System
        function openModal(modalId) {{
            document.getElementById(modalId).classList.add('active');
            document.body.style.overflow = 'hidden';
        }}

        function closeModal(modalId) {{
            document.getElementById(modalId).classList.remove('active');
            document.body.style.overflow = '';
        }}

        // Close modal on overlay click
        document.addEventListener('click', function(e) {{
            if (e.target.classList.contains('modal-overlay')) {{
                e.target.classList.remove('active');
                document.body.style.overflow = '';
            }}
        }});

        // Logout function
        function logout() {{
            localStorage.removeItem('token');
            window.location.href = '/';
        }}

        // HTMX Event Handling
        document.body.addEventListener('htmx:afterRequest', function(evt) {{
            if (evt.detail.successful) {{
                const trigger = evt.detail.requestConfig.triggeringEvent;
                if (trigger && trigger.target) {{
                    const successMsg = trigger.target.getAttribute('data-success-msg');
                    if (successMsg) {{
                        showToast(successMsg, 'success');
                    }}
                }}
            }} else {{
                showToast('Erro na requisição', 'error');
            }}
        }});
    </script>
</body>
</html>"""


def get_empty_state(icon: str, title: str, description: str, action_button: str = "") -> str:
    """Get empty state component."""
    return f"""
    <div class="text-center py-12">
        <div class="text-gray-400 text-6xl mb-4">
            <i class="fas {icon}"></i>
        </div>
        <h3 class="text-lg font-medium text-gray-900 mb-2">{title}</h3>
        <p class="text-gray-500 mb-6">{description}</p>
        {action_button}
    </div>
    """


def get_status_badge(status: str) -> str:
    """Get status badge HTML."""
    badges = {
        "active": '<span class="badge badge-success"><i class="fas fa-check mr-1"></i>Ativo</span>',
        "inactive": '<span class="badge badge-neutral"><i class="fas fa-pause mr-1"></i>Inativo</span>',
        "draft": '<span class="badge badge-warning"><i class="fas fa-pencil-alt mr-1"></i>Rascunho</span>',
        "archived": '<span class="badge badge-error"><i class="fas fa-archive mr-1"></i>Arquivado</span>',
        "completed": '<span class="badge badge-success"><i class="fas fa-check mr-1"></i>Concluído</span>',
        "failed": '<span class="badge badge-error"><i class="fas fa-times mr-1"></i>Falhou</span>',
        "running": '<span class="badge badge-warning"><i class="fas fa-spinner fa-spin mr-1"></i>Executando</span>',
        "pending": '<span class="badge badge-neutral"><i class="fas fa-clock mr-1"></i>Pendente</span>',
    }
    return badges.get(status.lower(), f'<span class="badge badge-neutral">{status}</span>')


def get_trigger_icon(trigger_type: str) -> str:
    """Get trigger type icon."""
    icons = {
        "webhook": "fa-bell",
        "scheduled": "fa-clock",
        "manual": "fa-hand-pointer",
        "file_upload": "fa-file-upload",
    }
    return icons.get(trigger_type.lower(), "fa-question")

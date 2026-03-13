from dataclasses import dataclass

from app.bot.keyboards import back_menu_keyboard
from app.bot.ux import classify_publication_error, format_schedule, human_draft_status, human_mode_label, human_publication_error, human_publication_status


@dataclass(slots=True)
class ChannelSummary:
    id: str
    title: str
    mode: str
    status: str


@dataclass(slots=True)
class AgentSummary:
    id: str
    name: str
    role: str
    model: str
    enabled: bool


@dataclass(slots=True)
class ContentPlanSummary:
    id: str
    period: str
    date_range: str
    status: str
    tasks_count: int


@dataclass(slots=True)
class DraftSummary:
    id: str
    title: str
    status: str
    version: int


@dataclass(slots=True)
class PublicationSummary:
    id: str
    title: str
    status: str
    scheduled_for: str | None



def channels_list_screen(channels: list[ChannelSummary]):
    if not channels:
        return {
            'text': (
                'Мои каналы\n'
                'У тебя пока нет каналов или подключённых проектов.\n\n'
                'Что можно сделать дальше:\n'
                '• создать первый проект канала\n'
                '• вернуться в главное меню'
            ),
            'buttons': [['Создать канал'], ['Главное меню']],
        }
    buttons = [[channel.title] for channel in channels]
    buttons += [['Создать канал'], ['Главное меню']]
    return {'text': 'Мои каналы', 'buttons': buttons}



def channel_dashboard_screen(title: str, mode: str, agents_count: int, content_plans_count: int = 0, drafts_count: int = 0) -> dict:
    return {
        'text': (
            f'Канал: {title}\n'
            f'Режим: {human_mode_label(mode)}\n'
            f'Агентов: {agents_count}\n'
            f'Контент-планов: {content_plans_count}\n'
            f'Черновиков: {drafts_count}\n\n'
            'Открой нужный раздел ниже: настройки, команда, черновики, публикации или режим работы.'
        ),
        'buttons': [
            ['Настройки'],
            ['Агенты'],
            ['Контент-план'],
            ['Черновики'],
            ['Публикации'],
            ['Режим работы'],
            ['Назад к каналам'],
            ['Главное меню'],
        ],
    }



def section_screen(title: str, body: str, buttons: list[list[str]] | None = None) -> dict:
    return {'text': f'{title}\n{body}', 'buttons': buttons or back_menu_keyboard()}



def channel_settings_screen(project_name: str, topic: str | None, language: str, content_format: str | None, posting_frequency: str | None, operation_mode: str) -> dict:
    body = (
        f'Проект: {project_name}\n'
        f'Тема: {topic or "—"}\n'
        f'Язык: {language}\n'
        f'Формат: {content_format or "—"}\n'
        f'Частота: {posting_frequency or "—"}\n'
        f'Режим проекта: {operation_mode}'
    )
    return section_screen('Настройки канала', body)



def channel_agents_screen(agents: list[AgentSummary]) -> dict:
    if not agents:
        body = (
            'Агенты пока не настроены.\n\n'
            'Когда команда агентов будет собрана, здесь появятся роли, модели и статус каждого участника.'
        )
    else:
        lines = [f'Всего агентов: {len(agents)}', '']
        for agent in agents:
            state = 'включён' if agent.enabled else 'выключен'
            lines.append(f'• {agent.name} — {agent.role} / {agent.model} / {state}')
        body = '\n'.join(lines)
    return section_screen('Агенты', body)



def channel_content_plan_screen(plans: list[ContentPlanSummary], tasks_total: int) -> dict:
    if not plans:
        body = (
            'Контент-планов пока нет.\n\n'
            'Сначала сгенерируй идеи или создай первый план, чтобы увидеть здесь периоды и задачи.'
        )
    else:
        lines = [f'Планов: {len(plans)}', f'Всего задач: {tasks_total}', '']
        for plan in plans[:5]:
            lines.append(f'• {plan.period} / {plan.date_range} / {plan.status} / задач: {plan.tasks_count}')
        body = '\n'.join(lines)
    return section_screen('Контент-план', body)



def channel_drafts_screen(drafts: list[DraftSummary]) -> dict:
    if not drafts:
        body = (
            'Черновиков пока нет.\n\n'
            'Как только появятся задачи и генерация контента, здесь будут лежать все новые и отредактированные черновики.'
        )
        buttons = back_menu_keyboard()
    else:
        lines = [f'Черновиков: {len(drafts)}', '', 'Открой нужный черновик кнопкой ниже:']
        buttons = []
        for draft in drafts[:7]:
            lines.append(f'• {draft.title} / {human_draft_status(draft.status)} / v{draft.version}')
            buttons.append([draft.title])
        buttons += [['Назад'], ['Главное меню']]
        body = '\n'.join(lines)
    return section_screen('Черновики', body, buttons=buttons)



def draft_detail_screen(title: str, status: str, version: int, text: str, created_by_agent: str | None = None) -> dict:
    preview = text if len(text) <= 900 else text[:897] + '...'
    body = (
        f'Задача: {title}\n'
        f'Статус: {human_draft_status(status)}\n'
        f'Версия: v{version}\n'
        f'Автор: {created_by_agent or "—"}\n\n'
        f'{preview}'
    )
    return section_screen(
        'Черновик',
        body,
        buttons=[
            ['Approve', 'Reject'],
            ['Edit draft', 'Regenerate'],
            ['Create publication'],
            ['Черновики'],
            ['Главное меню'],
        ],
    )



def publications_screen(publications: list[PublicationSummary]) -> dict:
    if not publications:
        return section_screen(
            'Публикации',
            'Публикаций пока нет.\n\nКогда из черновика будет создан пост, здесь появятся очередь, расписание и статус отправки.'
        )

    lines = [f'Публикаций: {len(publications)}', '']
    buttons: list[list[str]] = []
    for publication in publications[:7]:
        schedule = format_schedule(publication.scheduled_for)
        lines.append(f'• {publication.title} / {human_publication_status(publication.status)} / {schedule}')
        buttons.append([publication.title])
    buttons += [['Назад'], ['Главное меню']]
    return section_screen('Публикации', '\n'.join(lines), buttons=buttons)



def publication_detail_screen(title: str, status: str, scheduled_for: str | None, error_message: str | None = None) -> dict:
    classification = classify_publication_error(error_message)
    error_block = human_publication_error(error_message)
    next_step = ''
    if classification == 'temporary':
        next_step = '\nСледующее действие: подожди и попробуй Publish now ещё раз или переставь публикацию по времени.'
    elif classification == 'terminal':
        next_step = '\nСледующее действие: проверь права бота, канал и конфиг подключения перед повторной попыткой.'

    body = (
        f'Пост: {title}\n'
        f'Статус: {human_publication_status(status)}\n'
        f'Запланировано: {format_schedule(scheduled_for)}\n'
        f'Ошибка: {error_block}'
        f'{next_step}'
    )
    return section_screen(
        'Публикация',
        body,
        buttons=[
            ['Publish now', 'Schedule publication'],
            ['Cancel publication'],
            ['Публикации'],
            ['Главное меню'],
        ],
    )



def mode_screen(current_mode: str) -> dict:
    body = (
        f'Текущий режим канала: {human_mode_label(current_mode)}\n\n'
        'manual — пользователь подтверждает ключевые шаги вручную\n'
        'semi_auto — бот ведёт очередь и scheduled-публикации, но важные решения остаются у пользователя\n'
        'auto — канал работает максимально автоматически'
    )
    return section_screen(
        'Режим работы',
        body,
        buttons=[
            ['Mode: manual'],
            ['Mode: semi_auto'],
            ['Mode: auto'],
            ['Назад'],
            ['Главное меню'],
        ],
    )

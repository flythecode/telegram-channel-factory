from dataclasses import dataclass

from app.bot.keyboards import back_menu_keyboard
from app.bot.ux import classify_publication_error, format_schedule, human_draft_status, human_mode_label, human_publication_error, human_publication_status


def _format_generation_overview(summary: dict | None) -> str:
    if not summary:
        return ''
    queue = summary.get('queue') or {}
    plan = summary.get('plan') or {}
    guardrails = summary.get('guardrails') or {}
    lines = ['', 'Generation status:']
    lines.append(f"• Тариф: {plan.get('label') or plan.get('code') or '—'}")
    lines.append(f"• Статус плана: {plan.get('status_label') or plan.get('status') or plan.get('access_flag') or '—'}")
    lines.append(
        f"• Очередь: queued {queue.get('queued', 0)} / processing {queue.get('processing', 0)} / failed {queue.get('failed', 0)}"
    )
    latest_status = queue.get('latest_status')
    if latest_status:
        lines.append(f'• Последняя generation job: {latest_status}')
    latest_error = queue.get('latest_error')
    if latest_error:
        lines.append(f'• Последняя ошибка: {latest_error}')
    quota_used = plan.get('generation_used')
    quota_limit = plan.get('generation_limit')
    quota_remaining = plan.get('generation_remaining')
    if quota_limit is not None:
        lines.append(f"• Лимит generation: {quota_used or 0}/{quota_limit}")
    if quota_remaining is not None:
        lines.append(f"• Остаток generation: {quota_remaining}")
    period_end = plan.get('period_end')
    if period_end:
        lines.append(f'• Лимит действует до: {period_end}')
    block_reason = plan.get('block_reason')
    if plan.get('is_blocked') and block_reason:
        lines.append(f'• Причина блокировки: {block_reason}')
    elif guardrails.get('hard_stop_reached'):
        reasons = '; '.join(guardrails.get('blocking_reasons') or []) or 'лимит исчерпан'
        lines.append(f'• Генерация недоступна: {reasons}')
    elif guardrails.get('soft_limit_reached'):
        lines.append('• Лимиты почти исчерпаны: generation скоро может заблокироваться')
    return '\n'.join(lines)


def _format_draft_generation_details(summary: dict | None) -> str:
    overview = _format_generation_overview(summary)
    if not summary:
        return overview
    generation = summary.get('generation') or {}
    lines = [overview] if overview else []
    if generation.get('provider') or generation.get('model'):
        lines.append(f"• Provider/model: {generation.get('provider') or '—'} / {generation.get('model') or '—'}")
    if generation.get('finish_reason') == 'provider_unavailable':
        lines.append('• Provider сейчас деградировал: результат собран через graceful degradation/fallback path')
    elif generation.get('finish_reason'):
        lines.append(f"• Итог generation: {generation.get('finish_reason')}")
    if generation.get('failover_activated'):
        outcome = generation.get('failover_outcome') or 'activated'
        fallback_provider = generation.get('fallback_provider')
        suffix = f' → {fallback_provider}' if fallback_provider else ''
        lines.append(f'• Failover: {outcome}{suffix}')
    if generation.get('primary_error_message'):
        lines.append(f"• Ошибка provider’а: {generation.get('primary_error_message')}")
    return '\n'.join(line for line in lines if line)


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
                '• Следующий шаг один: нажми «Создать канал».\n'
                '• Я проведу тебя через запуск, подключение и первые публикации без ручного поиска по меню.'
            ),
            'buttons': [['Создать канал'], ['Главное меню']],
        }
    buttons = [[channel.title] for channel in channels]
    buttons += [['Создать канал'], ['Главное меню']]
    return {
        'text': (
            'Мои каналы\n'
            'Открой нужный канал кнопкой ниже — я верну тебя прямо в рабочую точку проекта.\n\n'
            'Если хочешь запустить новый канал отдельно, нажми «Создать канал». '
            'Разработчик для этого пути не нужен.'
        ),
        'buttons': buttons,
    }



def channel_dashboard_screen(title: str, mode: str, agents_count: int, content_plans_count: int = 0, drafts_count: int = 0, generation_summary: dict | None = None) -> dict:
    next_step = 'Следующий шаг: открой «Контент-план», чтобы запустить первый рабочий цикл.'
    if content_plans_count > 0 and drafts_count == 0:
        next_step = 'Следующий шаг: открой «Контент-план» и сгенерируй идеи или первые черновики.'
    elif drafts_count > 0:
        next_step = 'Следующий шаг: открой «Черновики» и выбери текст, который хочешь проверить или опубликовать.'
    return {
        'text': (
            f'Канал: {title}\n'
            f'Режим: {human_mode_label(mode)}\n'
            f'Агентов: {agents_count}\n'
            f'Контент-планов: {content_plans_count}\n'
            f'Черновиков: {drafts_count}\n'
            f'{_format_generation_overview(generation_summary)}\n\n'
            f'{next_step}\n'
            'Остальные разделы ниже нужны, когда захочешь изменить настройки, команду, публикации или режим работы.'
        ),
        'buttons': [
            ['⚙️ Настройки', '🤖 Агенты'],
            ['🗂 План', '📝 Черновики'],
            ['📢 Посты', '🎛 Режим'],
            ['⬅️ К каналам', '🏠 Главное меню'],
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
        f'Режим проекта: {operation_mode}\n\n'
        'Следующий рабочий шаг один: выбери, что менять — режим проекта или параметры, которые задавались в wizard.'
    )
    return section_screen('Настройки канала', body, buttons=[['✏️ Редактировать проект', '🛠 Режим работы'], ['⬅️ Назад', '🏠 Главное меню']])



def channel_project_edit_screen(project_name: str, topic: str | None, language: str, goal: str | None, content_format: str | None, posting_frequency: str | None, description: str | None) -> dict:
    body = (
        f'Проект: {project_name}\n'
        f'Тема/ниша: {topic or "—"}\n'
        f'Язык: {language}\n'
        f'Цель: {goal or "—"}\n'
        f'Формат: {content_format or "—"}\n'
        f'Частота: {posting_frequency or "—"}\n'
        f'Описание: {description or "—"}\n\n'
        'Следующий рабочий шаг один: выбери конкретный пункт для редактирования.'
    )
    return section_screen(
        'Редактировать проект',
        body,
        buttons=[
            ['✏️ Название', '✏️ Ниша'],
            ['✏️ Язык', '✏️ Цель'],
            ['✏️ Формат', '✏️ Частота'],
            ['✏️ Описание'],
            ['⬅️ Назад', '🏠 Главное меню'],
        ],
    )



def channel_agents_screen(agents: list[AgentSummary]) -> dict:
    if not agents:
        body = (
            'Агенты пока не настроены.\n\n'
            'Когда команда агентов будет собрана, здесь появятся роли, модели и статус каждого участника.\n'
            'Если ты уже создал проект, вернись назад и пройди рекомендуемый пресет — это самый короткий путь.'
        )
    else:
        lines = [f'Всего агентов: {len(agents)}', '', 'Команда собрана. Дополнительных действий здесь не нужно.', 'Следующий рабочий шаг: вернись в «Контент-план» и запусти идеи или черновики.', '']
        for agent in agents:
            state = 'включён' if agent.enabled else 'выключен'
            lines.append(f'• {agent.name} — {agent.role} / {agent.model} / {state}')
        body = '\n'.join(lines)
    return section_screen('Агенты', body)



def channel_content_plan_screen(plans: list[ContentPlanSummary], tasks_total: int, generation_summary: dict | None = None) -> dict:
    if not plans:
        body = (
            'Контент-планов пока нет.\n'
            f'{_format_generation_overview(generation_summary)}\n\n'
            'Следующий шаг: нажми «Создать контент-план».\n'
            'Сначала сгенерируй идеи или создай первый план, чтобы увидеть здесь периоды и задачи.\n'
            'После этого я помогу перейти к первым черновикам.'
        )
        buttons = [['Создать контент-план', '💡 10 идей'], ['⬅️ Назад', '🏠 Главное меню']]
    else:
        lines = [f'Планов: {len(plans)}', f'Всего задач: {tasks_total}']
        overview = _format_generation_overview(generation_summary)
        if overview:
            lines.extend(['', *overview.splitlines()])
        lines.extend(['', 'Следующий шаг: сгенерируй идеи или сразу создай первые 3 черновика.', ''])
        for plan in plans[:5]:
            lines.append(f'• {plan.period} / {plan.date_range} / {plan.status} / задач: {plan.tasks_count}')
        body = '\n'.join(lines)
        buttons = [['💡 Сгенерировать 10 идей', '📝 Создать 3 черновика'], ['⬅️ Назад', '🏠 Главное меню']]
    return section_screen('Контент-план', body, buttons=buttons)



def channel_drafts_screen(drafts: list[DraftSummary]) -> dict:
    if not drafts:
        body = (
            'Черновиков пока нет.\n\n'
            'Следующий шаг один: нажми «Создать 3 черновика».\n'
            'Как только генерация завершится, вернись сюда и открой нужный текст для проверки — здесь будут лежать все новые и отредактированные черновики.'
        )
        buttons = [['📝 Создать 3 черновика'], ['⬅️ Назад', '🏠 Главное меню']]
    else:
        lines = [f'Черновиков: {len(drafts)}', '', 'Следующий шаг один: открой нужный черновик кнопкой ниже.', '']
        buttons = []
        for draft in drafts[:7]:
            lines.append(f'• {draft.title} / {human_draft_status(draft.status)} / v{draft.version}')
            buttons.append([draft.title])
        buttons += [['⬅️ Назад', '🏠 Главное меню']]
        body = '\n'.join(lines)
    return section_screen('Черновики', body, buttons=buttons)



def draft_detail_screen(title: str, status: str, version: int, text: str, created_by_agent: str | None = None, generation_summary: dict | None = None) -> dict:
    preview = text if len(text) <= 900 else text[:897] + '...'
    generation_block = _format_draft_generation_details(generation_summary)
    generation_suffix = f'\n{generation_block}' if generation_block else ''
    body = (
        f'Задача: {title}\n'
        f'Статус: {human_draft_status(status)}\n'
        f'Версия: v{version}\n'
        f'Автор: {created_by_agent or "—"}'
        f'{generation_suffix}\n\n'
        f'{preview}'
    )
    return section_screen(
        'Черновик',
        body,
        buttons=[
            ['✅ Подтвердить', '🗑 Отклонить'],
            ['✏️ Редактировать', '🔁 Пересобрать'],
            ['📢 В пост', '📝 Черновики'],
            ['🏠 Главное меню'],
        ],
    )



def publications_screen(publications: list[PublicationSummary]) -> dict:
    if not publications:
        return section_screen(
            'Публикации',
            'Публикаций пока нет.\n\nСледующий шаг один: открой любой готовый черновик и нажми «Создать публикацию». После этого здесь появятся очередь, расписание и статус отправки.'
        )

    lines = [f'Публикаций: {len(publications)}', '', 'Следующий шаг один: открой нужную публикацию кнопкой ниже, чтобы отправить её сейчас или поставить в расписание.', '']
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
        next_step = '\nСледующее действие: подожди и попробуй «Опубликовать сейчас» ещё раз или переставь публикацию по времени.'
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
            ['🚀 Опубликовать', '🕒 Запланировать'],
            ['🗑 Отменить публикацию', '📢 Посты'],
            ['🏠 Главное меню'],
        ],
    )



def mode_screen(current_mode: str) -> dict:
    body = (
        f'Текущий режим канала: {human_mode_label(current_mode)}\n\n'
        'Ручной — пользователь подтверждает ключевые шаги вручную\n'
        'Ассистент — бот ведёт очередь и публикации по расписанию, но важные решения остаются у пользователя\n'
        'Авто — канал работает максимально автоматически'
    )
    return section_screen(
        'Режим работы',
        body,
        buttons=[
            ['✋ Ручной', '🤝 Ассистент'],
            ['⚡ Авто'],
            ['⬅️ Назад', '🏠 Главное меню'],
        ],
    )

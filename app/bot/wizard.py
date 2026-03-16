from dataclasses import dataclass, field

from app.bot.keyboards import back_menu_keyboard, project_ready_keyboard


SUMMARY_DESCRIPTION_PREVIEW_LIMIT = 700


def _summary_preview(value: str | None, limit: int = SUMMARY_DESCRIPTION_PREVIEW_LIMIT) -> str:
    if not value:
        return '—'
    compact = ' '.join(value.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + '…'


CHANNEL_CREATION_GUIDE_TEXT = (
    'Если канала ещё нет, создай его прямо в Telegram:\n\n'
    '1. Открой Telegram → «Новый канал».\n'
    '2. Задай название и описание.\n'
    '3. Сделай канал публичным или сохрани invite link.\n'
    '4. Добавь этого бота в администраторы.\n'
    '5. Вернись сюда и пришли @username канала.\n\n'
    'Когда канал уже создан — нажми «У меня уже есть канал».\n'
    'Если канал публичный, пришли формат вроде @my_channel.'
)


@dataclass(slots=True)
class ProjectWizardState:
    name: str | None = None
    niche: str | None = None
    language: str | None = None
    goal: str | None = None
    description: str | None = None
    content_format: str | None = None
    posting_frequency: str | None = None
    preset_code: str | None = None
    channel_ref: str | None = None
    connection_confirmed: bool = False


@dataclass(slots=True)
class WizardScreen:
    step: str
    text: str
    buttons: list[list[str]] = field(default_factory=list)


class ProjectWizardService:
    def start(self) -> WizardScreen:
        return WizardScreen(
            step='start',
            text=(
                'Создадим проект канала шаг за шагом. '
                'Я задам 7 коротких вопросов и после каждого шага покажу, что делать дальше.\n\n'
                'Первое действие сейчас: нажми «Начать».'
            ),
            buttons=[["Начать"], ["Главное меню"]],
        )

    def step_name(self) -> WizardScreen:
        return WizardScreen(
            step='name',
            text='Шаг 1/7 — напиши название проекта. Это внутреннее имя, его можно будет изменить позже.',
            buttons=back_menu_keyboard(),
        )

    def step_niche(self) -> WizardScreen:
        return WizardScreen(
            step='niche',
            text='Шаг 2/7 — выбери тему канала. Если вариант не подходит, нажми «Свой вариант» и продолжай.',
            buttons=[["AI", "Крипта"], ["Маркетинг", "Новости"], ["Свой вариант"], ["Назад"], ["Главное меню"]],
        )

    def step_language(self) -> WizardScreen:
        return WizardScreen(
            step='language',
            text='Шаг 3/7 — выбери основной язык публикаций.',
            buttons=[["Русский", "English"], ["Назад"], ["Главное меню"]],
        )

    def step_goal(self) -> WizardScreen:
        return WizardScreen(
            step='goal',
            text='Шаг 4/7 — выбери, зачем тебе канал. Это поможет подобрать подачу и будущий контент.',
            buttons=[["Личный бренд"], ["Трафик / лиды"], ["Экспертный контент"], ["Назад"], ["Главное меню"]],
        )

    def step_description(self) -> WizardScreen:
        return WizardScreen(
            step='description',
            text=(
                'Шаг 5/7 — добавь контекст проекта. Можешь прислать его несколькими сообщениями подряд: '
                'кто аудитория, что хочешь доносить, какая подача нужна, что важно и чего избегать.\n\n'
                'Когда закончишь — нажми «Готово». Если хочешь начать заново — нажми «Очистить». '
                'Если пока пропускаешь шаг — нажми «Пропустить».\n\n'
                'Пример: «Канал про ИИ-агентов для предпринимателей и аналитиков. Тон уверенный и практичный, '
                'без инфоцыганства. Даём кейсы, разборы инструментов и прикладную пользу».'
            ),
            buttons=[['Готово', 'Очистить'], ['Пропустить'], ['Назад'], ['Главное меню']],
        )

    def step_content_format(self) -> WizardScreen:
        return WizardScreen(
            step='content_format',
            text='Шаг 6/7 — выбери формат, в котором тебе удобнее вести канал.',
            buttons=[["Короткие посты"], ["Аналитика"], ["Смешанный формат"], ["Назад"], ["Главное меню"]],
        )

    def step_posting_frequency(self) -> WizardScreen:
        return WizardScreen(
            step='posting_frequency',
            text='Шаг 7/7 — выбери желаемую частоту публикаций. Это ориентир, а не жёсткое ограничение.',
            buttons=[["Ежедневно"], ["2 раза в день"], ["Несколько раз в неделю"], ["Назад"], ["Главное меню"]],
        )

    def summary(self, state: ProjectWizardState) -> WizardScreen:
        text = (
            'Проверь настройки проекта перед сохранением:\n'
            f'• Название: {state.name or "—"}\n'
            f'• Ниша: {state.niche or "—"}\n'
            f'• Язык: {state.language or "—"}\n'
            f'• Цель: {state.goal or "—"}\n'
            f'• Описание проекта: {_summary_preview(state.description)}\n'
            f'• Формат: {state.content_format or "—"}\n'
            f'• Частота: {state.posting_frequency or "—"}\n\n'
            'Следующий шаг один: нажми «Подтвердить проект».\n'
            'Если нужно что-то поменять, нажми «Назад» и поправь только нужный пункт.'
        )
        return WizardScreen(step='summary', text=text, buttons=[["Подтвердить проект"], ["Назад"], ["Главное меню"]])

    def preset_step(self) -> WizardScreen:
        return WizardScreen(
            step='preset',
            text=(
                'Теперь выбери команду AI-агентов.\n\n'
                '• 3 агента — самый простой и быстрый старт;\n'
                '• 5 агентов — баланс скорости и качества;\n'
                '• 7 агентов — больше редактуры и контроля.\n\n'
                'Если хочешь пройти путь без лишних решений, нажми «3 агента — Быстрый старт». '
                'Это рекомендуемый вариант для первого запуска.'
            ),
            buttons=[["3 агента — Быстрый старт"], ["5 агентов — Сбалансировано"], ["7 агентов — Полная редакция"], ["Назад"], ["Главное меню"]],
        )

    def channel_connect_step(self) -> WizardScreen:
        return WizardScreen(
            step='channel_connect',
            text=(
                'Осталось подключить твой Telegram-канал.\n\n'
                'Самый короткий путь:\n'
                '1. Нажми «У меня уже есть канал».\n'
                '2. Открой настройки канала в Telegram.\n'
                '3. Добавь этого бота в администраторы канала.\n'
                '4. Выдай право на публикацию сообщений.\n'
                '5. Пришли сюда @username канала.\n'
                '6. Нажми «Проверить подключение».\n\n'
                'Если канала ещё нет — нажми «Как создать канал».\n'
                'Пример username: @my_channel'
            ),
            buttons=[["У меня уже есть канал"], ["Как создать канал"], ["Проверить подключение"], ["Назад"], ["Главное меню"]],
        )

    def project_ready(self) -> WizardScreen:
        return WizardScreen(
            step='project_ready',
            text='Проект готов. Следующий шаг один: нажми «Создать контент-план». После этого я проведу к идеям и первым черновикам.',
            buttons=project_ready_keyboard(),
        )

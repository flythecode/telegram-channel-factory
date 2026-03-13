from dataclasses import dataclass, field

from app.bot.keyboards import back_menu_keyboard, project_ready_keyboard


@dataclass(slots=True)
class ProjectWizardState:
    name: str | None = None
    niche: str | None = None
    language: str | None = None
    goal: str | None = None
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
            text='Создадим проект канала шаг за шагом. Сначала задай название проекта.',
            buttons=[["Начать"], ["Главное меню"]],
        )

    def step_name(self) -> WizardScreen:
        return WizardScreen(step='name', text='Шаг 1/6 — введи название проекта.', buttons=back_menu_keyboard())

    def step_niche(self) -> WizardScreen:
        return WizardScreen(
            step='niche',
            text='Шаг 2/6 — выбери нишу канала.',
            buttons=[["AI", "Крипта"], ["Маркетинг", "Новости"], ["Свой вариант"], ["Назад"], ["Главное меню"]],
        )

    def step_language(self) -> WizardScreen:
        return WizardScreen(
            step='language',
            text='Шаг 3/6 — выбери язык канала.',
            buttons=[["Русский", "English"], ["Назад"], ["Главное меню"]],
        )

    def step_goal(self) -> WizardScreen:
        return WizardScreen(
            step='goal',
            text='Шаг 4/6 — выбери цель канала.',
            buttons=[["Личный бренд"], ["Трафик / лиды"], ["Экспертный контент"], ["Назад"], ["Главное меню"]],
        )

    def step_content_format(self) -> WizardScreen:
        return WizardScreen(
            step='content_format',
            text='Шаг 5/6 — выбери формат контента.',
            buttons=[["Короткие посты"], ["Аналитика"], ["Смешанный формат"], ["Назад"], ["Главное меню"]],
        )

    def step_posting_frequency(self) -> WizardScreen:
        return WizardScreen(
            step='posting_frequency',
            text='Шаг 6/6 — выбери частоту публикаций.',
            buttons=[["Ежедневно"], ["2 раза в день"], ["Несколько раз в неделю"], ["Назад"], ["Главное меню"]],
        )

    def summary(self, state: ProjectWizardState) -> WizardScreen:
        text = (
            'Проверь настройки проекта:\n'
            f'• Название: {state.name or "—"}\n'
            f'• Ниша: {state.niche or "—"}\n'
            f'• Язык: {state.language or "—"}\n'
            f'• Цель: {state.goal or "—"}\n'
            f'• Формат: {state.content_format or "—"}\n'
            f'• Частота: {state.posting_frequency or "—"}'
        )
        return WizardScreen(step='summary', text=text, buttons=[["Подтвердить проект"], ["Назад"], ["Главное меню"]])

    def preset_step(self) -> WizardScreen:
        return WizardScreen(
            step='preset',
            text='Выбери команду агентов для канала.',
            buttons=[["3 агента — Быстрый старт"], ["5 агентов — Сбалансировано"], ["7 агентов — Полная редакция"], ["Назад"], ["Главное меню"]],
        )

    def channel_connect_step(self) -> WizardScreen:
        return WizardScreen(
            step='channel_connect',
            text=(
                'Подключи Telegram-канал:\n'
                '1. Добавь бота в админы канала.\n'
                '2. Включи право на публикацию сообщений.\n'
                '3. Пришли сюда @username канала или channel_id.\n'
                '4. После этого нажми «Проверить подключение». '
            ),
            buttons=[["Повторить инструкцию"], ["Проверить подключение"], ["Назад"], ["Главное меню"]],
        )

    def project_ready(self) -> WizardScreen:
        return WizardScreen(
            step='project_ready',
            text='Проект готов. Можно перейти к рабочим действиям.',
            buttons=project_ready_keyboard(),
        )

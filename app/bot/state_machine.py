from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CallbackSpec:
    name: str
    value: str


CALLBACKS = {
    'main_create_channel': CallbackSpec('main_create_channel', 'main:create_channel'),
    'main_my_channels': CallbackSpec('main_my_channels', 'main:my_channels'),
    'main_help': CallbackSpec('main_help', 'main:help'),
    'main_how_it_works': CallbackSpec('main_how_it_works', 'main:how_it_works'),
    'wizard_start': CallbackSpec('wizard_start', 'wizard:start'),
    'wizard_next_name': CallbackSpec('wizard_next_name', 'wizard:name'),
    'wizard_next_niche': CallbackSpec('wizard_next_niche', 'wizard:niche'),
    'wizard_next_language': CallbackSpec('wizard_next_language', 'wizard:language'),
    'wizard_next_goal': CallbackSpec('wizard_next_goal', 'wizard:goal'),
    'wizard_next_content_format': CallbackSpec('wizard_next_content_format', 'wizard:content_format'),
    'wizard_next_frequency': CallbackSpec('wizard_next_frequency', 'wizard:posting_frequency'),
    'wizard_summary': CallbackSpec('wizard_summary', 'wizard:summary'),
    'wizard_preset': CallbackSpec('wizard_preset', 'wizard:preset'),
    'wizard_channel_connect': CallbackSpec('wizard_channel_connect', 'wizard:channel_connect'),
    'wizard_project_ready': CallbackSpec('wizard_project_ready', 'wizard:project_ready'),
}


class BotStates:
    START = 'start'
    MAIN_MENU = 'main_menu'
    WIZARD_NAME = 'wizard_name'
    WIZARD_NICHE = 'wizard_niche'
    WIZARD_LANGUAGE = 'wizard_language'
    WIZARD_GOAL = 'wizard_goal'
    WIZARD_CONTENT_FORMAT = 'wizard_content_format'
    WIZARD_POSTING_FREQUENCY = 'wizard_posting_frequency'
    WIZARD_SUMMARY = 'wizard_summary'
    WIZARD_PRESET = 'wizard_preset'
    WIZARD_CHANNEL_CONNECT = 'wizard_channel_connect'
    PROJECT_READY = 'project_ready'
    MY_CHANNELS = 'my_channels'
    CHANNEL_DASHBOARD = 'channel_dashboard'
    CHANNEL_SETTINGS = 'channel_settings'
    CHANNEL_AGENTS = 'channel_agents'
    CHANNEL_CONTENT_PLAN = 'channel_content_plan'
    CHANNEL_DRAFTS = 'channel_drafts'
    CHANNEL_PUBLICATIONS = 'channel_publications'
    CHANNEL_MODE = 'channel_mode'

from app.bot.app import resolve_screen_for_text, session_store


def test_description_step_accumulates_multiple_messages_until_done():
    chat_id = 888001
    session_store.clear(chat_id)
    session_store.set_step(chat_id, 'description')

    first = resolve_screen_for_text('Первый блок контекста.', chat_id=chat_id)
    second = resolve_screen_for_text('Второй блок контекста.', chat_id=chat_id)
    done = resolve_screen_for_text('Готово', chat_id=chat_id)

    assert 'Контекст сохранён в буфер' in first.text
    assert 'Контекст сохранён в буфер' in second.text
    state = session_store.get_state(chat_id)
    assert state.description == 'Первый блок контекста.\n\nВторой блок контекста.'
    assert 'Шаг 6/7' in done.text


def test_description_step_can_clear_buffer():
    chat_id = 888002
    session_store.clear(chat_id)
    session_store.set_step(chat_id, 'description')

    resolve_screen_for_text('Текст для удаления.', chat_id=chat_id)
    cleared = resolve_screen_for_text('Очистить', chat_id=chat_id)

    assert 'Буфер контекста очищен' in cleared.text
    assert session_store.get_meta(chat_id, 'description_buffer') == ''

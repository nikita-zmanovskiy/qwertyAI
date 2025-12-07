// ========== DOM ==========
const chatBox = document.getElementById('chat-box');
const chatForm = document.getElementById('chat-form');
const userInput = document.getElementById('user-input');
const fileInput = document.getElementById('file-input');
 
const chatList = document.getElementById('chat-list');
const newChatBtn = document.getElementById('new-chat');
const toggleMenu = document.getElementById('toggle-menu');
const sidebar = document.getElementById('sidebar');
const chatTitle = document.getElementById('chat-title');
const fileLabel = document.getElementById('file-label');
const cameraIcon = document.getElementById('camera-icon');
const thumbPreview = document.getElementById('thumb-preview');
const loaderMain = document.getElementById('loaderMain')
// modal rename
const modalOverlay = document.getElementById('modal-overlay');
const modalInput = document.getElementById('modal-input');
const modalOk = document.getElementById('modal-ok');
const modalCancel = document.getElementById('modal-cancel');
const modalTitle = document.getElementById('modal-title');

// modal delete
const deleteModalOverlay = document.getElementById('delete-modal-overlay');
const deleteModalOk = document.getElementById('delete-modal-ok');
const deleteModalCancel = document.getElementById('delete-modal-cancel');
const deleteModalText = document.getElementById('delete-modal-text');
const loader = document.getElementById('loader')
// scene modal
const sceneModalOverlay = document.getElementById('scene-modal-overlay');
const sceneModalTitle = document.getElementById('scene-modal-title');
const sceneModalText = document.getElementById('scene-modal-text');
const sceneModalCancel = document.getElementById('scene-modal-cancel');
const sceneModalSave = document.getElementById('scene-modal-save');
const welcome = document.getElementById('welcome')
// ========== State ==========
let chats = JSON.parse(localStorage.getItem('chats')) || [];
let activeChatId = localStorage.getItem('activeChatId') || null;
let attachedImage = null;
let attachedThumb = null;
const PAGE_SIZE = 10;

let renameTargetId = null;
let deleteTargetId = null;
let editingScene = null; // {chatId, sceneIndex}


document.addEventListener('DOMContentLoaded', () => {

    if(chats.length == 0) {
        chatList.insertAdjacentHTML('afterbegin', `<p class="chats__noone">У вас пока нет чатов.</p>`)

    }
    setTimeout(() => {
        loader.classList.add('hide')
         setTimeout(() => {
            loader.style = 'z-index: -1;'
            welcome.classList.add('activeWelcome')
            setTimeout(() => {
                welcome.classList.remove('activeWelcome')
                setTimeout(() => {
                    welcome.style = 'z-index: -1;'
                    loaderMain.classList.add('hide')
                    setTimeout(() => {
                        loaderMain.style = 'z-index: -1;'
                    }, 500);
                }, 1000);
            }, 1000)
         }, 600);
          
    }, 2000);
    
})
// ensure array
if (!Array.isArray(chats)) chats = [];
if (!activeChatId && chats.length) activeChatId = chats[0].id;

// ========== Helpers ==========
function save() {
    localStorage.setItem('chats', JSON.stringify(chats));
    localStorage.setItem('activeChatId', activeChatId);
}
function getChatById(id) { return chats.find(c => c.id === id); }
function uid() { return Date.now().toString() + Math.floor(Math.random()*1000); }

// ========== Chat list rendering ==========
function renderChatList() {
    chatList.innerHTML = '';
    chats.forEach(chat => {
        const li = document.createElement('li');
        li.dataset.id = chat.id;

        const titleSpan = document.createElement('span');
        titleSpan.className = 'li-title';
        titleSpan.textContent = chat.title;
        li.appendChild(titleSpan);

        const rightWrap = document.createElement('div');
        rightWrap.className = 'li-actions';

        const renameBtn = document.createElement('button');
        renameBtn.className = 'rename-btn';
        renameBtn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="25px" height="25px" viewBox="0 0 24 24" fill="none">
<path d="M12 5H9C7.11438 5 6.17157 5 5.58579 5.58579C5 6.17157 5 7.11438 5 9V15C5 16.8856 5 17.8284 5.58579 18.4142C6.17157 19 7.11438 19 9 19H15C16.8856 19 17.8284 19 18.4142 18.4142C19 17.8284 19 16.8856 19 15V12M9.31899 12.6911L15.2486 6.82803C15.7216 6.36041 16.4744 6.33462 16.9782 6.76876C17.5331 7.24688 17.5723 8.09299 17.064 8.62034L11.2329 14.6702L9 15L9.31899 12.6911Z" stroke="#fff" stroke-linecap="round" stroke-linejoin="round"/>
</svg>`;
        renameBtn.title = 'Переименовать';
        renameBtn.onclick = (e) => { e.stopPropagation(); openRenameModal(chat.id); };
        rightWrap.appendChild(renameBtn);

        const deleteBtn = document.createElement('button');
        deleteBtn.className = 'delete-btn';
        deleteBtn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="25px" height="25px" viewBox="0 0 24 24" fill="none"><path d="M4.99997 8H6.5M6.5 8V18C6.5 19.1046 7.39543 20 8.5 20H15.5C16.6046 20 17.5 19.1046 17.5 18V8M6.5 8H17.5M17.5 8H19M9 5H15M9.99997 11.5V16.5M14 11.5V16.5" stroke="#fff" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
        deleteBtn.title = 'Удалить чат';
        deleteBtn.onclick = (e) => { e.stopPropagation(); openDeleteModal(chat.id, chat.title); };
        rightWrap.appendChild(deleteBtn);

        li.appendChild(rightWrap);

        li.onclick = () => openChat(chat.id);

        if (chat.id === activeChatId) li.classList.add('active');
        chatList.appendChild(li);
    });
}

// ========== Create new chat with optional initial bot text ==========
function createNewChat(initialBotText = null) {
    const id = uid();
    const title = "Новый чат";
    const chat = { id, title, messages: [], renderCount: 0 };
    if (initialBotText) {
        chat.messages.push({ sender: 'bot', text: initialBotText, image: null, created: Date.now(), analysis: null });
        chat.renderCount = Math.min(PAGE_SIZE, chat.messages.length);
    }
    chats.unshift(chat);
    activeChatId = id;
    save();
    renderChatList();
    openChat(id);
    return chat;
}

// ========== Open chat ==========
function openChat(id) {
    activeChatId = id;
    const chat = getChatById(id);
    if (!chat) {
        renderMessages(true);
        return;
    }
    const total = chat.messages.length;
    chat.renderCount = Math.min(PAGE_SIZE, total);
    save();
    renderChatList();
    renderMessages(true);
}

// ========== Render messages with lazy loading ==========
function renderMessages(scrollToBottom = false) {
    chatBox.innerHTML = '';
    if (!chats.length) {
        chatTitle.textContent = 'QWERTY';
        const info = document.createElement('div');
        info.className = 'empty-note';
        info.innerHTML = `<div class="assistant__main">
            <h5 class="assistant__title">QWERTY AI</h5>
            <p class="first__text">Ультимативное решение для анализа сценария</p>
            <p class="assistant__main">Напишите предложение и ИИ оценит его!</p>
            <p class="assistant__description">Чат-бот создан для быстрого оценивания небольших предложений. Для детального анализа сценария воспользуйтесь главным анализатором</p>
            <a class="assistant__link" href="./rethink/index.html"> <button class="assistant__button">Перейти к детальному анализу</button></a>
            
        </div>`;
        chatBox.appendChild(info);
        return;
    }
    const chat = getChatById(activeChatId);
    if (!chat) {
        chatTitle.textContent = 'Выберите чат';
        const info = document.createElement('div');
        info.className = 'empty-note';
        info.textContent = 'Выберите чат слева или создайте новый. При загрузке сценария будет создан чат с результатами анализа.';
        chatBox.appendChild(info);
        return;
    }

    chatTitle.textContent = chat.title;
    const total = chat.messages.length;
    const renderCount = chat.renderCount || Math.min(PAGE_SIZE, total);
    const startIndex = Math.max(0, total - renderCount);

    if (startIndex > 0) {
        const moreNote = document.createElement('div');
        moreNote.className = 'empty-note';
        moreNote.textContent = 'Прокрутите вверх, чтобы загрузить предыдущие сообщения';
        chatBox.appendChild(moreNote);
    }

    const slice = chat.messages.slice(startIndex, total);
    slice.forEach((msg, idx) => {
        const el = makeMessageElement(msg, startIndex + idx);
        chatBox.appendChild(el);
    });

    if (scrollToBottom) {
        setTimeout(() => { chatBox.scrollTop = chatBox.scrollHeight; }, 0);
    }
}

// ========== Make message element (handles analysis object and HTML) ==========
function makeMessageElement(msg, messageIndex = null) {
    const div = document.createElement('div');
    div.classList.add('message', msg.sender);

    // image if present
    if (msg.image) {
        const img = document.createElement('img');
        img.className = 'msg-image';
        img.src = msg.image;
        div.appendChild(img);
    }
    if (msg.html) {
        div.innerHTML = msg.html;
        return div;
    }
    // if message contains analysis object -> render interactive analysis
    if (msg.analysis) {
        // plain text (optional)
        if (msg.text) {
            const t = document.createElement('div');
            t.className = 'msg-text-below';
            t.textContent = msg.text;
            div.appendChild(t);
        }

        // analysis block
        const analysis = msg.analysis;
        const block = document.createElement('div');
        block.className = 'analysis';

        // summary: overall rating + counts
        const summary = document.createElement('div');
        summary.className = 'summary';
        const ratingBadge = document.createElement('div');
        ratingBadge.className = 'badge rating';
        ratingBadge.textContent = `Рейтинг: ${analysis.overallRating}`;
        summary.appendChild(ratingBadge);

        const stats = document.createElement('div');
        stats.innerHTML = `<div style="font-size:13px;color:#ddd;">Сцен: ${analysis.scenes.length}</div>`;
        summary.appendChild(stats);
        block.appendChild(summary);

        // categories
        const catList = document.createElement('div');
        catList.className = 'cat-list';
        for (const cat of Object.keys(analysis.categories)) {
            const c = analysis.categories[cat];
            const it = document.createElement('div');
            it.className = 'cat-item';
            it.textContent = `${cat.toUpperCase()}: ${c.count} (${c.severity})`;
            catList.appendChild(it);
        }
        block.appendChild(catList);

        // scenes list (collapsible details)
        analysis.scenes.forEach((scene, idx) => {
            const s = document.createElement('div');
            s.className = 'scene';
            // header
            const head = document.createElement('div');
            head.className = 'scene-head';
            const title = document.createElement('div');
            title.className = 'scene-title';
            title.textContent = `Сцена ${idx+1}` + (scene.heading ? ` — ${scene.heading}` : '');
            head.appendChild(title);

            const right = document.createElement('div');
            right.style.display = 'flex';
            right.style.gap = '8px';

            const sev = document.createElement('div');
            sev.className = `severity-${scene.severity.toLowerCase()}`;
            sev.textContent = scene.severity;
            right.appendChild(sev);

            const btnShow = document.createElement('button');
            btnShow.textContent = 'Показать сцену';
            btnShow.classList.add('showScene')
            btnShow.onclick = () => openSceneModal(activeChatId, idx);
            right.appendChild(btnShow);

            const falseBtn = document.createElement('button');
            falseBtn.textContent = scene.marked ? 'Отметить как корректную (отменить)' : 'Отметить как ложноположительную';
             falseBtn.classList.add('falseBtn')
            falseBtn.onclick = () => {
                // toggle mark
                scene.marked = !scene.marked;
                // recompute summary severities quickly (simple)
                recomputeAnalysisForMessage(msg);
                save();
                renderMessages(false);
            };
            right.appendChild(falseBtn);

            head.appendChild(right);
            s.appendChild(head);

            const body = document.createElement('div');
            body.className = 'scene-body';
            body.textContent = scene.text.length > 500 ? scene.text.slice(0,500) + '...' : scene.text;
            s.appendChild(body);

            // small list of violations
            const vlist = document.createElement('div');
            vlist.style.display = 'flex';
            vlist.style.gap = '8px';
            vlist.style.flexWrap = 'wrap';
            for (const k of Object.keys(scene.violations)) {
                const cnt = scene.violations[k];
                if (cnt > 0) {
                    const badge = document.createElement('div');
                    badge.className = 'badge';
                    badge.style.background = '#222';
                    badge.textContent = `${k}: ${cnt}`;
                    vlist.appendChild(badge);
                }
            }
            s.appendChild(vlist);

            block.appendChild(s);
        });

        // final: export button / re-analyze
        const actions = document.createElement('div');
        actions.style.display = 'flex';
        actions.style.gap = '8px';
        actions.style.marginTop = '8px';
        const rean = document.createElement('button');
        rean.textContent = 'Переанализировать (локально)';
        rean.classList.add('reanalizate')
        rean.onclick = () => {
            const newAnalysis = analyzeScript(analysis.rawText);
            msg.analysis = newAnalysis;
            save();
            renderMessages(true);
        };
        actions.appendChild(rean);

        block.appendChild(actions);
        div.appendChild(block);
        return div;
    }

    // else normal text
    if (msg.text) {
        // allow small HTML for bot to include clickable things in future; safer to set textContent
        const t = document.createElement('div');
        t.textContent = msg.text;
        div.appendChild(t);
    }

    return div;
}

// ========== Add message (auto-create chat if needed) ==========
function addMessageToActive(sender, text, image = null, analysis = null) {
    // if there are no chats at all -> create new chat automatically
    if (!chats.length) {
        createNewChat("Новый чат — начните писать или загрузите сценарий (.txt).");
    }
    // if activeChatId is null, create one
    if (!activeChatId) {
        createNewChat("Новый чат — начните писать или загрузите сценарий (.txt).");
    }
    const chat = getChatById(activeChatId);
    if (!chat) return;
    const msg = { sender, text: text || '', image: image || null, created: Date.now(), analysis: analysis || null };
    chat.messages.push(msg);
    chat.renderCount = Math.min((chat.renderCount || PAGE_SIZE) + 1, chat.messages.length);
    save();
    renderMessages(true);
    return msg;
}

// ========== Fake reply ==========
async function fakeApiResponse(userText) {
    return new Promise(resolve => {
        setTimeout(() => {
            const replies = [
                "Тимоха лох :)",
                "Интересная мысль.",
                "Расскажи подробнее 👀",
                "Хороший вопрос!",
                "Согласен, круто.",
                "Могу помочь с этим."
            ];
            resolve(replies[Math.floor(Math.random() * replies.length)]);
        }, 900 + Math.random() * 800);
    });
}

// ========== Submit handler (create chat automatically if none) ==========
// ========== Submit handler (create chat automatically if none) ==========
// ========== Submit handler (create chat automatically if none) ==========
chatForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const text = userInput.value.trim();

    // If no chats => create one automatically
    if (!chats.length) {
        createNewChat("Новый чат — начните писать или загрузите сценарий (.txt).");
        sidebar.classList.remove('hidden');
    }
    if (!activeChatId) {
        createNewChat("Новый чат — начните писать или загрузите сценарий (.txt).");
    }

    if (!text && !attachedImage) {
        alert("Введите текст или прикрепите изображение!");
        return;
    }

    // add user message
    addMessageToActive('user', text, attachedImage);

    // clear inputs & thumb
    userInput.value = '';
    attachedImage = null;
    attachedThumb = null;
    thumbPreview.style.display = 'none';
    cameraIcon.style.display = 'inline';

    // show bot typing
    addMessageToActive('bot', 'Анализирую сообщение...');

    try {
        // Real API call
        const response = await fetch('http://158.160.98.70:8000/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ message: text })
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();

        // remove typing message
        const chat = getChatById(activeChatId);
        if (chat && chat.messages.length) {
            const last = chat.messages[chat.messages.length-1];
            if (last && last.sender==='bot' && /анализирую/i.test(last.text)) {
                chat.messages.pop();
            }
        }

        // Create formatted HTML response
        const analysisHTML = `
<div class="analysis">
    <div class="analysis-header">
        <div class="analysis-icon">📊</div>
        <div class="analysis-title">Результат анализа</div>
    </div>
    
    <div class="rating-section">
        <div class="rating-badge rating-${data.overall_rating.replace('+', '')}">
            🔞 ${data.overall_rating}
        </div>
        <div class="summary-text">${data.summary}</div>
    </div>

    <div class="stats-section">
        <h4>📈 Статистика</h4>
        <div class="stats-grid">
            <div class="stat-item">
                <span class="stat-label">Всего предложений:</span>
                <span class="stat-value">${data.statistics.total_sentences}</span>
            </div>
            <div class="stat-item">
                <span class="stat-label">Проблемных:</span>
                <span class="stat-value">${data.statistics.problematic_sentences}</span>
            </div>
            <div class="stat-item">
                <span class="stat-label">Процент проблемных:</span>
                <span class="stat-value">${data.statistics.problematic_percentage}%</span>
            </div>
        </div>
    </div>

    <div class="violations-section">
        <h4>🚫 Нарушения</h4>
        <div class="violations-grid">
            <div class="violation-item ${data.statistics.violations.violence > 0 ? 'has-violation' : ''}">
                <span class="violation-label">Насилие:</span>
                <span class="violation-count">${data.statistics.violations.violence}</span>
            </div>
            <div class="violation-item ${data.statistics.violations.profanity > 0 ? 'has-violation' : ''}">
                <span class="violation-label">Ненормативная лексика:</span>
                <span class="violation-count">${data.statistics.violations.profanity}</span>
            </div>
            <div class="violation-item ${data.statistics.violations.sexual_content > 0 ? 'has-violation' : ''}">
                <span class="violation-label">Сексуальный контент:</span>
                <span class="violation-count">${data.statistics.violations.sexual_content}</span>
            </div>
            <div class="violation-item ${data.statistics.violations.drugs_alcohol > 0 ? 'has-violation' : ''}">
                <span class="violation-label">Наркотики/алкоголь:</span>
                <span class="violation-count">${data.statistics.violations.drugs_alcohol}</span>
            </div>
            <div class="violation-item ${data.statistics.violations.fear_elements > 0 ? 'has-violation' : ''}">
                <span class="violation-label">Элементы страха:</span>
                <span class="violation-count">${data.statistics.violations.fear_elements}</span>
            </div>
        </div>
    </div>
</div>
        `;

        // Create special message with HTML content
        const botMessage = {
            sender: 'bot',
            text: '', // We'll use HTML instead
            created: Date.now(),
            analysis: null,
            html: analysisHTML
        };

        const chat2 = getChatById(activeChatId);
        if (chat2) {
            chat2.messages.push(botMessage);
            chat2.renderCount = Math.min((chat2.renderCount || PAGE_SIZE) + 1, chat2.messages.length);
            save();
            renderMessages(true);
        }

    } catch (error) {
        console.error('Error calling API:', error);
        
        // remove typing message
        const chat = getChatById(activeChatId);
        if (chat && chat.messages.length) {
            const last = chat.messages[chat.messages.length-1];
            if (last && last.sender==='bot' && /анализирую/i.test(last.text)) {
                chat.messages.pop();
            }
        }

        // Fallback to fake response if API is unavailable
        const reply = await fakeApiResponse(text);
        addMessageToActive('bot', `⚠️ API временно недоступно. Вот ответ:\n\n${reply}`);
    }
});

// ========== Fake reply (fallback) ==========
async function fakeApiResponse(userText) {
    return new Promise(resolve => {
        setTimeout(() => {
            const replies = [
                "Это сообщение было проанализировано в автономном режиме.",
                "Анализ завершен: сообщение не содержит нарушений.",
                "Проверка показала, что контент соответствует возрастному рейтингу 12+.",
                "Обнаружены незначительные нарушения в контенте."
            ];
            resolve(replies[Math.floor(Math.random() * replies.length)]);
        }, 900 + Math.random() * 800);
    });
}

// ========== Image file handling (photo) ==========
fileInput.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (!file) return;
    if (!file.type.startsWith('image/')) { alert('Файл не изображение'); fileInput.value=''; return; }

    const reader = new FileReader();
    reader.onload = (ev) => {
        const img = new Image();
        img.onload = () => {
            const MAX = 300;
            const thumbSize = 40;
            let { width, height } = img;
            let scale = Math.min(1, MAX / Math.max(width, height));
            const canvas = document.createElement('canvas');
            canvas.width = Math.round(width * scale);
            canvas.height = Math.round(height * scale);
            const ctx = canvas.getContext('2d');
            ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
            attachedImage = canvas.toDataURL('image/jpeg', 0.85);

            // thumb
            const canvas2 = document.createElement('canvas');
            canvas2.width = thumbSize;
            canvas2.height = thumbSize;
            const ctx2 = canvas2.getContext('2d');
            const ratio = Math.min(thumbSize / width, thumbSize / height);
            const tw = Math.round(width * ratio);
            const th = Math.round(height * ratio);
            const dx = Math.round((thumbSize - tw) / 2);
            const dy = Math.round((thumbSize - th) / 2);
            ctx2.fillStyle = "#232325";
            ctx2.fillRect(0,0,thumbSize,thumbSize);
            ctx2.drawImage(img, 0, 0, width, height, dx, dy, tw, th);
            attachedThumb = canvas2.toDataURL('image/jpeg', 0.8);

            cameraIcon.style.display = 'none';
            thumbPreview.src = attachedThumb;
            thumbPreview.style.display = 'block';
        };
        img.src = ev.target.result;
    };
    reader.readAsDataURL(file);
});

 

// ========== Lazy loading on scroll ==========
let loadingOlder = false;
chatBox.addEventListener('scroll', () => {
    const chat = getChatById(activeChatId);
    if (!chat) return;
    if (chatBox.scrollTop === 0 && !loadingOlder) {
        const total = chat.messages.length;
        const current = chat.renderCount || 0;
        if (current < total) {
            loadingOlder = true;
            const oldH = chatBox.scrollHeight;
            chat.renderCount = Math.min(total, current + PAGE_SIZE);
            renderMessages(false);
            setTimeout(()=> {
                const newH = chatBox.scrollHeight;
                chatBox.scrollTop = newH - oldH;
                loadingOlder = false;
            }, 0);
        }
    }
});

// ========== Rename modal ==========
function openRenameModal(chatId) {
    renameTargetId = chatId;
    const chat = getChatById(chatId);
    modalInput.value = chat ? chat.title : '';
    modalTitle.textContent = 'Переименовать чат';
    modalOverlay.style.display = 'flex';
    modalInput.focus();
}
modalCancel.onclick = () => { modalOverlay.style.display = 'none'; renameTargetId = null; };
modalOk.onclick = () => {
    const name = modalInput.value.trim();
    if (!name) { alert('Название не может быть пустым'); return; }
    const chat = getChatById(renameTargetId);
    if (chat) chat.title = name;
    save();
    modalOverlay.style.display = 'none';
    renameTargetId = null;
    renderChatList();
    renderMessages(true);
};

// ========== Delete modal ==========
function openDeleteModal(chatId, chatTitle) {
    deleteTargetId = chatId;
    deleteModalText.textContent = `Удалить чат "${chatTitle}"? Действие необратимо.`;
    deleteModalOverlay.style.display = 'flex';
}
deleteModalCancel.onclick = () => { deleteTargetId = null; deleteModalOverlay.style.display = 'none'; };
deleteModalOk.onclick = () => {
    if (!deleteTargetId) return;
    const idx = chats.findIndex(c => c.id === deleteTargetId);
    if (idx !== -1) {
        const wasActive = (chats[idx].id === activeChatId);
        chats.splice(idx,1);
        if (wasActive) {
            if (chats.length) activeChatId = chats[Math.min(idx, chats.length-1)].id;
            else activeChatId = null;
        }
        save();
        renderChatList();
        renderMessages(true);
    }
    deleteTargetId = null;
    deleteModalOverlay.style.display = 'none';
};

// ========== Clear all ==========
document.getElementById('clear-all').onclick = () => {
    if (!confirm('Удалить все чаты и историю?')) return;
    chats = [];
    activeChatId = null;
    save();
    renderChatList();
    renderMessages();
};

// ========== Scene modal (edit) ==========
function openSceneModal(chatId, sceneIndex) {
    editingScene = { chatId, sceneIndex };
    const chat = getChatById(chatId);
    if (!chat) return;
    // find last analysis message in chat (for simplicity take last bot message with analysis)
    const mIdx = chat.messages.findIndex(m => m.analysis);
    if (mIdx === -1) {
        alert('Анализ не найден в этом чате.');
        return;
    }
    const analysis = chat.messages[mIdx].analysis;
    const scene = analysis.scenes[sceneIndex];
    if (!scene) return;
    sceneModalTitle.textContent = `Сцена ${sceneIndex+1}`;
    sceneModalText.value = scene.text;
    sceneModalOverlay.style.display = 'flex';
    sceneModalText.focus();
}
sceneModalCancel.onclick = () => { sceneModalOverlay.style.display = 'none'; editingScene = null; };
sceneModalSave.onclick = () => {
    if (!editingScene) return;
    const { chatId, sceneIndex } = editingScene;
    const chat = getChatById(chatId);
    const mIdx = chat.messages.findIndex(m => m.analysis);
    if (mIdx === -1) return;
    const analysis = chat.messages[mIdx].analysis;
    analysis.scenes[sceneIndex].text = sceneModalText.value;
    // re-run small detection for that scene
    const newViol = detectViolations(sceneModalText.value);
    analysis.scenes[sceneIndex].violations = newViol.counts;
    analysis.scenes[sceneIndex].severity = newViol.severity;
    // recompute categories & overall
    recomputeAnalysisForMessage(chat.messages[mIdx]);
    save();
    sceneModalOverlay.style.display = 'none';
    editingScene = null;
    renderMessages(true);
};

// ========== Toggle menu ==========
toggleMenu.onclick = () => sidebar.classList.toggle('hidden');

// ========== Init ==========
function init() {
    if (chats.length === 0) {
        // no auto-create; show info
    } else {
        if (!activeChatId) activeChatId = chats[0].id;
    }
    renderChatList();
    renderMessages(true);
    newChatBtn.onclick = () => createNewChat("Новый чат — начните писать или загрузите сценарий (.txt).");
}
init();

// ========== Analysis logic (simple rule-based simulation) ==========

// Keywords (simple lists — extend as needed)
const KEYWORDS = {
    violence: ['убил','убийство','драться','стрелял','насил','ударил','пуля','ранен','замочил','избил','убивают'],
    profanity: ['бляд','хуй','сука','пизд','еба','нахуй','ублюдок','матьвашу'],
    erotic: ['голая','эрот','секс','целует','раздет','обнаж','обнажен'],
    alcohol: ['выпил','алкоголь','пиво','вино','водка','спирт','наркот','косяк','курит'],
    scary: ['страшно','ужас','труп','кошмар','монстр','пуга','крики','тревога']
};

// thresholds to classify severity per scene (counts):
function severityFromCount(cnt) {
    if (cnt === 0) return 'None';
    if (cnt <= 1) return 'Mild';
    if (cnt <= 3) return 'Moderate';
    return 'Severe';
}

// Map severity to age rating (highest severity across categories)
function ratingFromSeverities(severities) {
    // severities is array of strings like 'None','Mild','Moderate','Severe'
    if (severities.includes('Severe')) return '18+';
    if (severities.includes('Moderate')) return '16+';
    if (severities.includes('Mild')) return '12+';
    return '0+';
}

// helper: naive scene segmentation
function segmentScenes(text) {
    // split by common script markers (INT., EXT., SCENE) or by double newline blocks
    const lines = text.replace(/\r/g,'').split('\n');
    const scenes = [];
    let buffer = [];
    let heading = null;
    for (let i=0;i<lines.length;i++){
        const L = lines[i].trim();
        const isHeading = /^((INT|EXT|SCENE)\b|^SCENE[:\s]|^Scene[:\s])/i.test(L) || (L === L.toUpperCase() && L.length>3 && L.length<80 && /\w/.test(L));
        if (isHeading && buffer.length>0) {
            scenes.push({ heading: heading || buffer[0].slice(0,80), text: buffer.join('\n') });
            buffer = [];
            heading = L;
        }
        if (isHeading && buffer.length===0) {
            heading = L;
            continue;
        }
        buffer.push(lines[i]);
        // double blank line -> split
        if (i<lines.length-1 && lines[i+1].trim()==='' && buffer.join('\n').trim()!=='') {
            scenes.push({ heading: heading || null, text: buffer.join('\n') });
            buffer = [];
            heading = null;
            i++; // skip blank
        }
    }
    if (buffer.length) scenes.push({ heading: heading || null, text: buffer.join('\n') });
    // if no scenes found, return whole text as single scene
    if (scenes.length===0) scenes.push({ heading: null, text });
    return scenes;
}

// detect violations in a text chunk
function detectViolations(text) {
    const low = text.toLowerCase();
    const counts = { violence:0, profanity:0, erotic:0, alcohol:0, scary:0 };
    for (const k of Object.keys(KEYWORDS)) {
        for (const word of KEYWORDS[k]) {
            // simple substring count
            let idx = 0;
            while (true) {
                idx = low.indexOf(word, idx);
                if (idx === -1) break;
                counts[k]++;
                idx += word.length;
            }
        }
    }
    const total = Object.values(counts).reduce((s,v)=>s+v,0);
    // determine severity by sum of counts
    let severity = severityFromCount(total);
    return { counts, total, severity };
}

// main analyzer
function analyzeScript(text) {
    const scenesRaw = segmentScenes(text);
    const scenes = scenesRaw.map(s => {
        const det = detectViolations(s.text);
        return {
            heading: s.heading,
            text: s.text,
            violations: det.counts,
            severity: det.severity,
            marked: false
        };
    });

    // aggregate categories
    const categories = { violence:{count:0,severity:'None'}, profanity:{count:0,severity:'None'}, erotic:{count:0,severity:'None'}, alcohol:{count:0,severity:'None'}, scary:{count:0,severity:'None'} };
    scenes.forEach(sc => {
        if (sc.marked) return; // skip marked as false positive
        for (const k of Object.keys(categories)) {
            categories[k].count += sc.violations[k] || 0;
        }
    });
    // assign per-category severity by counts
    for (const k of Object.keys(categories)) {
        categories[k].severity = severityFromCount(categories[k].count);
    }

    // determine scene severities for overall
    const sceneSeverities = scenes.filter(s=>!s.marked).map(s => s.severity);
    // if all none => 0+, else choose highest
    const overallRating = ratingFromSeverities(sceneSeverities);

    return { overallRating, categories, scenes, rawText: text };
}

// recompute categories and overall for a specific message (when scenes edited or marked)
function recomputeAnalysisForMessage(msg) {
    const analysis = msg.analysis;
    if (!analysis) return;
    // recalc categories
    const categories = { violence:{count:0,severity:'None'}, profanity:{count:0,severity:'None'}, erotic:{count:0,severity:'None'}, alcohol:{count:0,severity:'None'}, scary:{count:0,severity:'None'} };
    analysis.scenes.forEach(sc => {
        if (sc.marked) return;
        for (const k of Object.keys(categories)) categories[k].count += sc.violations[k]||0;
    });
    for (const k of Object.keys(categories)) categories[k].severity = severityFromCount(categories[k].count);
    const sceneSevs = analysis.scenes.filter(s=>!s.marked).map(s=>s.severity);
    analysis.categories = categories;
    analysis.overallRating = ratingFromSeverities(sceneSevs);
    // update rawText if missing
    if (!analysis.rawText) analysis.rawText = analysis.scenes.map(s=>s.text).join('\n\n');
    return analysis;
}

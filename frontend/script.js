// 상대 경로 사용: 어떤 도메인/IP로 접속하든 그 주소의 API를 그대로 호출
const API_BASE_URL = '/api';

let currentPlayer = null;
let gameState = {
    isLoading: false,
    messageHistory: [],
    storyArchive: [],
    restLocations: new Set(['교차로 마을'])  // can_rest 지역 (loadLocations에서 갱신)
};

const elements = {
    chatMessages: document.getElementById('chatMessages'),
    actionInput: document.getElementById('actionInput'),
    submitBtn: document.getElementById('submitBtn'),
    newGameBtn: document.getElementById('newGameBtn'),
    settingsBtn: document.getElementById('settingsBtn'),
    locationBadge: document.getElementById('locationBadge'),
    playerName: document.getElementById('playerName'),
    playerJob: document.getElementById('playerJob'),
    playerLevel: document.getElementById('playerLevel'),
    hpValue: document.getElementById('hpValue'),
    hpBarFill: document.getElementById('hpBarFill'),
    playerAttack: document.getElementById('playerAttack'),
    playerDefense: document.getElementById('playerDefense'),
    playerStrength: document.getElementById('playerStrength'),
    playerDexterity: document.getElementById('playerDexterity'),
    playerIntelligence: document.getElementById('playerIntelligence'),
    playerGold: document.getElementById('playerGold'),
    xpValue: document.getElementById('xpValue'),
    xpBarFill: document.getElementById('xpBarFill'),
    combatSection: document.getElementById('combatSection'),
    huntSection: document.getElementById('huntSection'),
    huntBtn: document.getElementById('huntBtn'),
    enemyName: document.getElementById('enemyName'),
    enemyLevel: document.getElementById('enemyLevel'),
    enemyHpValue: document.getElementById('enemyHpValue'),
    enemyHpBarFill: document.getElementById('enemyHpBarFill'),
    attackBtn: document.getElementById('attackBtn'),
    fleeBtn: document.getElementById('fleeBtn'),
    shopBtn: document.getElementById('shopBtn'),
    shopModal: document.getElementById('shopModal'),
    closeShopBtn: document.getElementById('closeShopBtn'),
    shopGold: document.getElementById('shopGold'),
    buyTabBtn: document.getElementById('buyTabBtn'),
    sellTabBtn: document.getElementById('sellTabBtn'),
    shopBuyList: document.getElementById('shopBuyList'),
    shopSellList: document.getElementById('shopSellList'),
    restBtn: document.getElementById('restBtn'),
    travelList: document.getElementById('travelList'),
    questBoardBtn: document.getElementById('questBoardBtn'),
    questModal: document.getElementById('questModal'),
    closeQuestBtn: document.getElementById('closeQuestBtn'),
    questActiveCount: document.getElementById('questActiveCount'),
    questOfferList: document.getElementById('questOfferList'),
    statsKills: document.getElementById('statsKills'),
    statsDeaths: document.getElementById('statsDeaths'),
    statsQuests: document.getElementById('statsQuests'),
    weaponSlotContent: document.getElementById('weaponSlotContent'),
    armorSlotContent: document.getElementById('armorSlotContent'),
    unequipWeaponBtn: document.getElementById('unequipWeaponBtn'),
    unequipArmorBtn: document.getElementById('unequipArmorBtn'),
    inventoryList: document.getElementById('inventoryList'),
    inventoryInfo: document.getElementById('inventoryInfo'),
    questList: document.getElementById('questList'),
    jobModal: document.getElementById('jobModal'),
    jobGrid: document.getElementById('jobGrid'),
    settingsModal: document.getElementById('settingsModal'),
    closeSettingsBtn: document.getElementById('closeSettingsBtn'),
    playerNameInput: document.getElementById('playerNameInput'),
    saveNameBtn: document.getElementById('saveNameBtn'),
    ollamaUrlInput: document.getElementById('ollamaUrlInput'),
    testOllamaBtn: document.getElementById('testOllamaBtn'),
    ollamaStatus: document.getElementById('ollamaStatus'),
    mpValue: document.getElementById('mpValue'),
    mpBarFill: document.getElementById('mpBarFill'),
    skillBtn: document.getElementById('skillBtn'),
    statusEffects: document.getElementById('statusEffects'),
    modelSelect: document.getElementById('modelSelect'),
    applyModelBtn: document.getElementById('applyModelBtn'),
    saveSlotList: document.getElementById('saveSlotList'),
};

async function initializeGame() {
    try {
        const response = await fetch(`${API_BASE_URL}/game/status`);
        const data = await response.json();
        currentPlayer = data.player;

        if (!currentPlayer.job_selected) {
            await showJobSelectionModal();
        } else {
            restoreChatHistory();
            addSystemMessage("게임이 로드되었습니다! 무엇을 하시겠습니까?");
            updateUI();
        }
    } catch (error) {
        console.error('Error loading game:', error);
        addSystemMessage('게임 로드에 실패했습니다. 백엔드 서버가 포트 8000에서 실행 중인지 확인하세요.');
    }
}

function restoreChatHistory() {
    // 서버에 저장된 최근 대화를 채팅창에 복원 (새로고침해도 이야기 유지)
    const history = currentPlayer.recent_history || [];
    if (history.length === 0) return;

    if (currentPlayer.story_summary) {
        addSystemMessage(`[지금까지의 이야기] ${currentPlayer.story_summary}`);
    }

    history.forEach(msg => {
        if (msg.role === '플레이어') {
            addPlayerMessage(msg.content);
        } else if (msg.role === '나레이터') {
            addNarratorMessage(msg.content);
        } else {
            addEventMessage(msg.content);
        }
    });
}

async function showJobSelectionModal() {
    try {
        const response = await fetch(`${API_BASE_URL}/game/jobs`);
        const data = await response.json();
        const jobs = data.jobs;

        let jobsHTML = '';
        for (const [jobId, jobInfo] of Object.entries(jobs)) {
            jobsHTML += `
                <div class="job-card" onclick="selectJob('${jobId}')">
                    <div class="job-card-name">${jobInfo.name}</div>
                    <div class="job-card-description">${jobInfo.description}</div>
                    <div class="job-card-stats">
                        <div class="job-stat-row">
                            <span class="job-stat-label">힘:</span>
                            <span class="job-stat-value">${jobInfo.strength}</span>
                        </div>
                        <div class="job-stat-row">
                            <span class="job-stat-label">민첩:</span>
                            <span class="job-stat-value">${jobInfo.dexterity}</span>
                        </div>
                        <div class="job-stat-row">
                            <span class="job-stat-label">지력:</span>
                            <span class="job-stat-value">${jobInfo.intelligence}</span>
                        </div>
                    </div>
                </div>
            `;
        }
        elements.jobGrid.innerHTML = jobsHTML;
        elements.jobModal.classList.remove('hidden');
    } catch (error) {
        console.error('Error loading jobs:', error);
        addSystemMessage('직업 선택을 불러오는데 실패했습니다.');
    }
}

async function selectJob(jobId) {
    try {
        const response = await fetch(`${API_BASE_URL}/game/select-job?job=${jobId}`, {
            method: 'POST'
        });
        const data = await response.json();
        currentPlayer = data.player;

        elements.jobModal.classList.add('hidden');
        addSystemMessage(data.message);

        // 고정 프롤로그를 서사로 출력 (한 단락씩 시간차를 두고)
        if (data.prologue && data.prologue.length > 0) {
            for (const paragraph of data.prologue) {
                addNarratorMessage(paragraph);
                await new Promise(resolve => setTimeout(resolve, 800));
            }
        }

        updateUI();
        elements.actionInput.focus();
    } catch (error) {
        console.error('Error selecting job:', error);
        addSystemMessage('직업 선택에 실패했습니다.');
    }
}

function addMessage(role, content, type = 'narrative') {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}`;

    const paragraph = document.createElement('p');
    paragraph.textContent = content;
    messageDiv.appendChild(paragraph);

    elements.chatMessages.appendChild(messageDiv);
    elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;

    gameState.messageHistory.push({ role, content, type });

    // 화면 표시용 정리: 500개 초과 시 오래된 메시지부터 제거
    // (AI 기억은 서버가 자동 관리하므로 화면만 정리하면 됨)
    if (gameState.messageHistory.length > 500) {
        gameState.messageHistory.shift();
        const firstMessage = elements.chatMessages.firstChild;
        if (firstMessage) {
            firstMessage.remove();
        }
    }
}

function addSystemMessage(content) {
    addMessage('system', content, 'system');
}

function addPlayerMessage(content) {
    addMessage('player', content, 'action');
}

function addNarratorMessage(content) {
    addMessage('narrator', content, 'narrative');
}

function startStreamingNarratorMessage() {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message narrator';

    const paragraph = document.createElement('p');
    messageDiv.appendChild(paragraph);

    elements.chatMessages.appendChild(messageDiv);
    elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;

    return paragraph;
}

function appendStreamChunk(paragraph, text) {
    paragraph.textContent += text;
    elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;
}

function finalizeStreamedMessage(content) {
    gameState.messageHistory.push({ role: 'narrator', content, type: 'narrative' });

    if (gameState.messageHistory.length > 500) {
        gameState.messageHistory.shift();
        const firstMessage = elements.chatMessages.firstChild;
        if (firstMessage) {
            firstMessage.remove();
        }
    }
}

function addEventMessage(content) {
    addMessage('event', content, 'event');
}

async function submitAction() {
    const actionText = elements.actionInput.value.trim();

    if (!actionText) {
        addSystemMessage('행동을 입력하세요.');
        return;
    }

    if (gameState.isLoading) {
        addSystemMessage('나레이터가 이야기를 마칠 때까지 기다려주세요...');
        return;
    }

    if (!currentPlayer) {
        addSystemMessage('게임이 로드되지 않았습니다. 페이지를 새로고침하세요.');
        return;
    }

    if (currentPlayer.current_enemy) {
        addSystemMessage('전투 중에는 행동할 수 없습니다. 공격 또는 도망 버튼을 사용하세요.');
        return;
    }

    gameState.isLoading = true;
    elements.submitBtn.disabled = true;
    elements.actionInput.disabled = true;

    addPlayerMessage(actionText);
    elements.actionInput.value = '';
    showTyping();

    let streamParagraph = null;

    try {
        const response = await fetch(`${API_BASE_URL}/game/action/stream`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: actionText })
        });

        if (!response.ok) {
            const error = await response.json();
            hideTyping();
            addSystemMessage(`오류: ${error.detail}`);
            return;
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop(); // 마지막 줄은 아직 완성 안 됐을 수 있음

            for (const line of lines) {
                if (!line.trim()) continue;
                const event = JSON.parse(line);

                if (event.type === 'chunk') {
                    if (!streamParagraph) {
                        hideTyping();
                        streamParagraph = startStreamingNarratorMessage();
                    }
                    appendStreamChunk(streamParagraph, event.text);
                } else if (event.type === 'done') {
                    currentPlayer = event.player;
                    finalizeStreamedMessage(event.narrative);

                    // 서사에서 추출된 실제 상태 변화 (골드/체력/아이템)
                    if (event.event_logs) {
                        event.event_logs.forEach(log => addEventMessage(log));
                    }

                    if (event.special_event) {
                        addEventMessage(event.special_event);
                    }

                    updateUI();
                }
            }
        }
    } catch (error) {
        console.error('Error performing action:', error);
        hideTyping();
        addSystemMessage('오류: ' + error.message);
    } finally {
        gameState.isLoading = false;
        elements.submitBtn.disabled = false;
        elements.actionInput.disabled = false;
        elements.actionInput.focus();
    }
}

function updateUI() {
    if (!currentPlayer) return;

    elements.playerName.textContent = currentPlayer.name;

    const jobNames = {
        "warrior": "전사",
        "rogue": "도적",
        "mage": "마법사",
        "paladin": "성기사",
        "ranger": "레인저"
    };
    elements.playerJob.textContent = jobNames[currentPlayer.job_class] || "미선택";
    elements.playerLevel.textContent = currentPlayer.level;
    elements.hpValue.textContent = `${currentPlayer.hp}/${currentPlayer.max_hp}`;
    elements.locationBadge.textContent = currentPlayer.location;

    const hpPercent = Math.max(0, (currentPlayer.hp / currentPlayer.max_hp) * 100);
    elements.hpBarFill.style.width = hpPercent + '%';

    // 정신력 (스킬 자원)
    const maxMp = currentPlayer.max_mp || 30;
    const mp = currentPlayer.mp ?? maxMp;
    elements.mpValue.textContent = `${mp}/${maxMp}`;
    elements.mpBarFill.style.width = Math.max(0, (mp / maxMp) * 100) + '%';

    // 백엔드에서 계산된 스탯 사용 (직업 보너스 + 장비 보너스 포함)
    elements.playerAttack.textContent = currentPlayer.effective_attack ?? currentPlayer.attack;
    elements.playerDefense.textContent = currentPlayer.effective_defense ?? currentPlayer.defense;

    elements.playerStrength.textContent = currentPlayer.strength;
    elements.playerDexterity.textContent = currentPlayer.dexterity;
    elements.playerIntelligence.textContent = currentPlayer.intelligence;

    // 골드, 경험치
    elements.playerGold.textContent = currentPlayer.gold ?? 0;
    const expRequired = currentPlayer.exp_required || (currentPlayer.level * 100);
    elements.xpValue.textContent = `${currentPlayer.experience}/${expRequired}`;
    const xpPercent = Math.min(100, (currentPlayer.experience / expRequired) * 100);
    elements.xpBarFill.style.width = xpPercent + '%';

    // 통계
    elements.statsKills.textContent = currentPlayer.stats_kills ?? 0;
    elements.statsDeaths.textContent = currentPlayer.stats_deaths ?? 0;
    elements.statsQuests.textContent = currentPlayer.stats_quests_completed ?? 0;

    // 여관 버튼은 휴식 가능 지역에서만 표시 (지역 데이터 기반)
    elements.restBtn.style.display = gameState.restLocations.has(currentPlayer.location) ? 'block' : 'none';

    updateCombatPanel();
    updateEquipmentSlots();
    updateInventory();
    updateQuests();
}

function updateCombatPanel() {
    const enemy = currentPlayer.current_enemy;

    if (enemy) {
        elements.combatSection.classList.remove('hidden');
        elements.huntSection.classList.add('hidden');
        elements.enemyName.textContent = enemy.name;
        elements.enemyLevel.textContent = enemy.level;
        elements.enemyHpValue.textContent = `${enemy.hp}/${enemy.max_hp}`;
        const enemyHpPercent = Math.max(0, (enemy.hp / enemy.max_hp) * 100);
        elements.enemyHpBarFill.style.width = enemyHpPercent + '%';
        elements.actionInput.disabled = true;
        elements.submitBtn.disabled = true;

        // 스킬 버튼: 이름 + 소모 정신력, 부족하면 비활성
        const skill = currentPlayer.skill;
        if (skill) {
            elements.skillBtn.textContent = `${skill.name} (${skill.mp_cost})`;
            elements.skillBtn.disabled = (currentPlayer.mp ?? 0) < skill.mp_cost;
            elements.skillBtn.title = skill.description;
        }

        // 상태 이상 표시
        const effects = currentPlayer.status_effects || [];
        const effectNames = { poison: '중독', stun: '기절' };
        elements.statusEffects.textContent = effects.length > 0
            ? '상태: ' + effects.map(e => `${effectNames[e.type] || e.type} ${e.turns}턴`).join(', ')
            : '';
    } else {
        elements.combatSection.classList.add('hidden');
        elements.huntSection.classList.remove('hidden');
        if (!gameState.isLoading) {
            elements.actionInput.disabled = false;
            elements.submitBtn.disabled = false;
        }
    }
}

async function startCombat() {
    if (gameState.isLoading) return;

    try {
        const response = await fetch(`${API_BASE_URL}/combat/start`, { method: 'POST' });

        if (!response.ok) {
            const error = await response.json();
            addSystemMessage(`오류: ${error.detail}`);
            return;
        }

        const data = await response.json();
        currentPlayer = data.player;
        data.logs.forEach(log => addEventMessage(log));
        updateUI();
    } catch (error) {
        console.error('Error starting combat:', error);
        addSystemMessage('전투 시작 오류: ' + error.message);
    }
}

async function combatAction(endpoint) {
    if (gameState.isLoading) return;
    gameState.isLoading = true;
    elements.attackBtn.disabled = true;
    elements.skillBtn.disabled = true;
    elements.fleeBtn.disabled = true;

    try {
        const response = await fetch(`${API_BASE_URL}/combat/${endpoint}`, { method: 'POST' });

        if (!response.ok) {
            const error = await response.json();
            addSystemMessage(`오류: ${error.detail}`);
            return;
        }

        const data = await response.json();
        currentPlayer = data.player;
        data.logs.forEach(log => addEventMessage(log));
        updateUI();
        if (data.combat_over) {
            loadLocations();
        }
    } catch (error) {
        console.error('Error in combat:', error);
        addSystemMessage('전투 오류: ' + error.message);
    } finally {
        gameState.isLoading = false;
        elements.attackBtn.disabled = false;
        elements.fleeBtn.disabled = false;
        updateCombatPanel();  // 스킬 버튼 활성화 여부는 여기서 MP 기준으로 재계산
    }
}

async function openShop() {
    if (currentPlayer && currentPlayer.current_enemy) {
        addSystemMessage('전투 중에는 상점을 이용할 수 없습니다.');
        return;
    }

    try {
        const response = await fetch(`${API_BASE_URL}/shop/list`);
        const data = await response.json();

        elements.shopGold.textContent = data.gold;

        elements.shopBuyList.innerHTML = data.stock.map(item => `
            <div class="shop-item">
                <div class="shop-item-info">
                    <div class="shop-item-name">${item.name}</div>
                    <div class="shop-item-desc">${item.description}</div>
                </div>
                <span class="shop-item-price">${item.price} G</span>
                <button class="btn btn-small" data-buy-item="${item.id}">구매</button>
            </div>
        `).join('');

        if (data.sellable.length === 0) {
            elements.shopSellList.innerHTML = '<div class="empty-message">판매할 수 있는 아이템이 없습니다</div>';
        } else {
            elements.shopSellList.innerHTML = data.sellable.map(item => `
                <div class="shop-item">
                    <div class="shop-item-info">
                        <div class="shop-item-name">${item.name} (x${item.quantity})</div>
                    </div>
                    <span class="shop-item-price">${item.sell_price} G</span>
                    <button class="btn btn-small" data-sell-item="${item.id}">판매</button>
                </div>
            `).join('');
        }

        document.querySelectorAll('[data-buy-item]').forEach(btn => {
            btn.addEventListener('click', () => buyItem(btn.dataset.buyItem));
        });
        document.querySelectorAll('[data-sell-item]').forEach(btn => {
            btn.addEventListener('click', () => sellItem(btn.dataset.sellItem));
        });

        elements.shopModal.classList.remove('hidden');
    } catch (error) {
        console.error('Error opening shop:', error);
        addSystemMessage('상점을 여는데 실패했습니다.');
    }
}

function closeShop() {
    elements.shopModal.classList.add('hidden');
}

function switchShopTab(tab) {
    if (tab === 'buy') {
        elements.buyTabBtn.classList.add('active');
        elements.sellTabBtn.classList.remove('active');
        elements.shopBuyList.classList.remove('hidden');
        elements.shopSellList.classList.add('hidden');
    } else {
        elements.sellTabBtn.classList.add('active');
        elements.buyTabBtn.classList.remove('active');
        elements.shopSellList.classList.remove('hidden');
        elements.shopBuyList.classList.add('hidden');
    }
}

async function buyItem(itemId) {
    try {
        const response = await fetch(`${API_BASE_URL}/shop/buy?item_id=${itemId}`, { method: 'POST' });
        const data = await response.json();

        if (!response.ok) {
            addSystemMessage(`오류: ${data.detail}`);
            return;
        }

        currentPlayer = data.player;
        addSystemMessage(data.message);
        updateUI();
        openShop();
    } catch (error) {
        console.error('Error buying item:', error);
        addSystemMessage('구매 오류: ' + error.message);
    }
}

async function sellItem(itemId) {
    try {
        const response = await fetch(`${API_BASE_URL}/shop/sell?item_id=${itemId}`, { method: 'POST' });
        const data = await response.json();

        if (!response.ok) {
            addSystemMessage(`오류: ${data.detail}`);
            return;
        }

        currentPlayer = data.player;
        addSystemMessage(data.message);
        updateUI();
        await openShop();
        switchShopTab('sell');
    } catch (error) {
        console.error('Error selling item:', error);
        addSystemMessage('판매 오류: ' + error.message);
    }
}

function updateEquipmentSlots() {
    if (currentPlayer.equipment.weapon) {
        const weapon = currentPlayer.equipment.weapon;
        elements.weaponSlotContent.innerHTML = `
            <div class="item-in-slot">
                <div class="item-name">${weapon.name}</div>
                <div class="item-effect">+${weapon.effect.attack_bonus || 0} ATK</div>
            </div>
        `;
        elements.unequipWeaponBtn.style.display = 'block';
    } else {
        elements.weaponSlotContent.innerHTML = '<div class="empty-slot">-</div>';
        elements.unequipWeaponBtn.style.display = 'none';
    }

    if (currentPlayer.equipment.armor) {
        const armor = currentPlayer.equipment.armor;
        elements.armorSlotContent.innerHTML = `
            <div class="item-in-slot">
                <div class="item-name">${armor.name}</div>
                <div class="item-effect">+${armor.effect.defense_bonus || 0} DEF</div>
            </div>
        `;
        elements.unequipArmorBtn.style.display = 'block';
    } else {
        elements.armorSlotContent.innerHTML = '<div class="empty-slot">-</div>';
        elements.unequipArmorBtn.style.display = 'none';
    }
}

function updateInventory() {
    const inventory = currentPlayer.inventory;
    elements.inventoryInfo.textContent = `${inventory.items.length}/${inventory.max_slots}`;

    if (inventory.items.length === 0) {
        elements.inventoryList.innerHTML = '<div class="empty-message">아이템이 없습니다</div>';
        return;
    }

    elements.inventoryList.innerHTML = inventory.items.map(item => `
        <div class="inventory-item">
            <span class="inventory-item-name">${item.name}</span>
            <div class="inventory-item-actions">
                <span class="inventory-item-qty">×${item.quantity}</span>
                ${getInventoryItemButtons(item)}
            </div>
        </div>
    `).join('');

    inventory.items.forEach(item => {
        const equipBtn = document.querySelector(`[data-equip-item="${item.id}"]`);
        const useBtn = document.querySelector(`[data-use-item="${item.id}"]`);

        if (equipBtn) {
            equipBtn.addEventListener('click', () => equipItem(item.id));
        }
        if (useBtn) {
            useBtn.addEventListener('click', () => useItem(item.id));
        }
    });
}

function getInventoryItemButtons(item) {
    if (item.item_type === 'weapon' || item.item_type === 'armor') {
        return `<button class="btn btn-small" data-equip-item="${item.id}">장착</button>`;
    } else if (item.item_type === 'consumable') {
        return `<button class="btn btn-small" data-use-item="${item.id}">사용</button>`;
    }
    return '';
}

async function equipItem(itemId) {
    try {
        const response = await fetch(`${API_BASE_URL}/inventory/equip?item_id=${itemId}`, {
            method: 'POST'
        });
        const data = await response.json();
        currentPlayer = data.player;
        addSystemMessage(data.message);
        updateUI();
    } catch (error) {
        console.error('Error equipping item:', error);
        addSystemMessage('아이템 장착 오류: ' + error.message);
    }
}

async function unequipItem(slot) {
    try {
        const response = await fetch(`${API_BASE_URL}/inventory/unequip?slot=${slot}`, {
            method: 'POST'
        });
        const data = await response.json();
        currentPlayer = data.player;
        addSystemMessage(data.message);
        updateUI();
    } catch (error) {
        console.error('Error unequipping item:', error);
        addSystemMessage('아이템 장착 해제 오류: ' + error.message);
    }
}

async function useItem(itemId) {
    try {
        const response = await fetch(`${API_BASE_URL}/inventory/use?item_id=${itemId}`, {
            method: 'POST'
        });
        const data = await response.json();
        currentPlayer = data.player;
        addSystemMessage(data.message);
        updateUI();
    } catch (error) {
        console.error('Error using item:', error);
        addSystemMessage('아이템 사용 오류: ' + error.message);
    }
}

function updateQuests() {
    const quests = currentPlayer.active_quests || [];
    const completed = currentPlayer.completed_quests || [];

    let html = '';

    if (quests.length === 0) {
        html += '<div class="empty-message">진행 중인 퀘스트가 없습니다</div>';
    } else {
        html += quests.map(q => `
            <div class="quest-item">
                ${q.title}
                <div class="quest-progress">진행: ${q.progress}/${q.target_count} | 보상: ${q.reward_gold}골드, 경험치 ${q.reward_xp}</div>
            </div>
        `).join('');
    }

    if (completed.length > 0) {
        const total = currentPlayer.stats_quests_completed ?? completed.length;
        html += `<div class="quest-completed-header">최근 완료 (누적 ${total}개)</div>`;
        html += completed.slice(-3).reverse().map(q => `
            <div class="quest-item completed">${q.title}</div>
        `).join('');
    }

    elements.questList.innerHTML = html;
}

// ===== 이동 시스템 =====

async function loadLocations() {
    try {
        const response = await fetch(`${API_BASE_URL}/game/locations`);
        const data = await response.json();

        // 휴식 가능 지역 갱신 (여관 버튼 표시에 사용)
        gameState.restLocations = new Set(
            data.locations.filter(loc => loc.can_rest).map(loc => loc.name)
        );

        elements.travelList.innerHTML = data.locations.map(loc => `
            <div class="travel-item ${loc.current ? 'current' : ''}" ${loc.current ? '' : `data-travel="${loc.name}"`}>
                <span class="travel-item-name">${loc.name}${loc.current ? ' (현재)' : ''}</span>
                <span class="travel-item-level">${loc.description}</span>
            </div>
        `).join('');

        document.querySelectorAll('[data-travel]').forEach(el => {
            el.addEventListener('click', () => travelTo(el.dataset.travel));
        });
    } catch (error) {
        console.error('Error loading locations:', error);
    }
}

async function travelTo(location) {
    if (gameState.isLoading) return;

    try {
        const response = await fetch(`${API_BASE_URL}/game/travel?location=${encodeURIComponent(location)}`, {
            method: 'POST'
        });
        const data = await response.json();

        if (!response.ok) {
            addSystemMessage(`오류: ${data.detail}`);
            return;
        }

        currentPlayer = data.player;
        addEventMessage(data.message);
        if (data.logs) {
            data.logs.forEach(log => addEventMessage(log));
        }
        updateUI();
        loadLocations();
    } catch (error) {
        console.error('Error traveling:', error);
        addSystemMessage('이동 오류: ' + error.message);
    }
}

async function restAtInn() {
    if (gameState.isLoading) return;

    try {
        const response = await fetch(`${API_BASE_URL}/game/rest`, { method: 'POST' });
        const data = await response.json();

        if (!response.ok) {
            addSystemMessage(`오류: ${data.detail}`);
            return;
        }

        currentPlayer = data.player;
        addEventMessage(data.message);
        updateUI();
    } catch (error) {
        console.error('Error resting:', error);
        addSystemMessage('휴식 오류: ' + error.message);
    }
}

// ===== 퀘스트 게시판 =====

async function openQuestBoard() {
    try {
        const response = await fetch(`${API_BASE_URL}/quest/available`);
        const data = await response.json();

        elements.questActiveCount.textContent = `${data.active_count}/${data.max_active}`;

        if (data.offers.length === 0) {
            elements.questOfferList.innerHTML = '<div class="empty-message">이 지역에는 의뢰가 없습니다</div>';
        } else {
            elements.questOfferList.innerHTML = data.offers.map(offer => `
                <div class="shop-item">
                    <div class="shop-item-info">
                        <div class="shop-item-name">${offer.title}</div>
                        <div class="shop-item-desc">보상: ${offer.reward_gold}골드, 경험치 ${offer.reward_xp}</div>
                    </div>
                    ${offer.already_active
                        ? '<span class="shop-item-price">진행 중</span>'
                        : `<button class="btn btn-small" data-accept-quest="${offer.id}">수락</button>`}
                </div>
            `).join('');

            document.querySelectorAll('[data-accept-quest]').forEach(btn => {
                btn.addEventListener('click', () => acceptQuest(btn.dataset.acceptQuest));
            });
        }

        elements.questModal.classList.remove('hidden');
    } catch (error) {
        console.error('Error opening quest board:', error);
        addSystemMessage('퀘스트 게시판을 여는데 실패했습니다.');
    }
}

function closeQuestBoard() {
    elements.questModal.classList.add('hidden');
}

async function acceptQuest(questId) {
    try {
        const response = await fetch(`${API_BASE_URL}/quest/accept?quest_id=${encodeURIComponent(questId)}`, {
            method: 'POST'
        });
        const data = await response.json();

        if (!response.ok) {
            addSystemMessage(`오류: ${data.detail}`);
            return;
        }

        currentPlayer = data.player;
        addSystemMessage(data.message);
        updateUI();
        openQuestBoard();
    } catch (error) {
        console.error('Error accepting quest:', error);
        addSystemMessage('퀘스트 수락 오류: ' + error.message);
    }
}

// ===== 나레이터 응답 대기 표시 =====

function showTyping() {
    const div = document.createElement('div');
    div.className = 'message narrator typing-indicator';
    div.id = 'typingIndicator';
    const p = document.createElement('p');
    p.textContent = '나레이터가 이야기를 쓰는 중...';
    div.appendChild(p);
    elements.chatMessages.appendChild(div);
    elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;
}

function hideTyping() {
    const el = document.getElementById('typingIndicator');
    if (el) el.remove();
}

async function startNewGame() {
    if (confirm('새 게임을 시작하시겠습니까? 진행 상황이 초기화됩니다.')) {
        gameState.messageHistory = [];
        elements.chatMessages.innerHTML = '';

        try {
            const response = await fetch(`${API_BASE_URL}/game/new`, {
                method: 'POST'
            });
            const data = await response.json();
            currentPlayer = data.player;
            addSystemMessage(data.message);

            if (!currentPlayer.job_selected) {
                await showJobSelectionModal();
            } else {
                updateUI();
                elements.actionInput.focus();
            }
        } catch (error) {
            console.error('Error starting new game:', error);
            addSystemMessage('새 게임 시작 오류: ' + error.message);
        }
    }
}

function openSettings() {
    elements.playerNameInput.value = currentPlayer.name;
    elements.settingsModal.classList.remove('hidden');
    loadModelList();
    loadSaveSlots();
}

// ===== AI 모델 선택 =====

async function loadModelList() {
    try {
        const response = await fetch(`${API_BASE_URL}/ollama/models`);
        const data = await response.json();

        if (data.models.length === 0) {
            elements.modelSelect.innerHTML = '<option value="">모델 목록을 불러올 수 없음 (Ollama 확인)</option>';
            return;
        }

        elements.modelSelect.innerHTML = data.models.map(m =>
            `<option value="${m}" ${m === data.current ? 'selected' : ''}>${m}${m === data.current ? ' (사용 중)' : ''}</option>`
        ).join('');
    } catch (error) {
        console.error('Error loading models:', error);
        elements.modelSelect.innerHTML = '<option value="">불러오기 실패</option>';
    }
}

async function applyModel() {
    const name = elements.modelSelect.value;
    if (!name) return;

    try {
        const response = await fetch(`${API_BASE_URL}/ollama/model?name=${encodeURIComponent(name)}`, {
            method: 'POST'
        });
        const data = await response.json();

        if (!response.ok) {
            addSystemMessage(`오류: ${data.detail}`);
            return;
        }

        addSystemMessage(data.message);
        loadModelList();
    } catch (error) {
        console.error('Error applying model:', error);
        addSystemMessage('모델 변경 실패: ' + error.message);
    }
}

// ===== 저장 슬롯 =====

async function loadSaveSlots() {
    try {
        const response = await fetch(`${API_BASE_URL}/saves`);
        const data = await response.json();

        elements.saveSlotList.innerHTML = data.slots.map(s => {
            let info;
            if (s.corrupted) {
                info = '<span class="save-slot-info">손상된 데이터</span>';
            } else if (s.exists) {
                const time = s.saved_at ? s.saved_at.replace('T', ' ') : '';
                info = `<div class="save-slot-info">Lv.${s.level} ${s.job} - ${s.location}<div class="save-slot-time">${time}</div></div>`;
            } else {
                info = '<span class="save-slot-info">빈 슬롯</span>';
            }

            return `
                <div class="save-slot">
                    <span class="save-slot-info">슬롯 ${s.slot}</span>
                    ${info}
                    <div class="save-slot-actions">
                        <button class="btn btn-small" data-save-slot="${s.slot}">저장</button>
                        ${s.exists && !s.corrupted ? `<button class="btn btn-small" data-load-slot="${s.slot}">불러오기</button>` : ''}
                    </div>
                </div>
            `;
        }).join('');

        document.querySelectorAll('[data-save-slot]').forEach(btn => {
            btn.addEventListener('click', () => saveToSlot(parseInt(btn.dataset.saveSlot)));
        });
        document.querySelectorAll('[data-load-slot]').forEach(btn => {
            btn.addEventListener('click', () => loadFromSlot(parseInt(btn.dataset.loadSlot)));
        });
    } catch (error) {
        console.error('Error loading save slots:', error);
        elements.saveSlotList.innerHTML = '<div class="empty-message">슬롯 정보를 불러올 수 없습니다</div>';
    }
}

async function saveToSlot(slot) {
    try {
        const response = await fetch(`${API_BASE_URL}/saves/save?slot=${slot}`, { method: 'POST' });
        const data = await response.json();

        if (!response.ok) {
            addSystemMessage(`오류: ${data.detail}`);
            return;
        }

        addSystemMessage(data.message);
        loadSaveSlots();
    } catch (error) {
        console.error('Error saving to slot:', error);
        addSystemMessage('저장 실패: ' + error.message);
    }
}

async function loadFromSlot(slot) {
    if (!confirm(`슬롯 ${slot}을 불러오시겠습니까? 현재 진행은 사라집니다. (필요하면 먼저 다른 슬롯에 저장하세요)`)) {
        return;
    }

    try {
        const response = await fetch(`${API_BASE_URL}/saves/load?slot=${slot}`, { method: 'POST' });
        const data = await response.json();

        if (!response.ok) {
            addSystemMessage(`오류: ${data.detail}`);
            return;
        }

        // 불러온 상태로 화면 전체 재구성 (대화 복원 포함)
        location.reload();
    } catch (error) {
        console.error('Error loading from slot:', error);
        addSystemMessage('불러오기 실패: ' + error.message);
    }
}

function closeSettings() {
    elements.settingsModal.classList.add('hidden');
}

async function savePlayerName() {
    const newName = elements.playerNameInput.value.trim();
    if (!newName) {
        addSystemMessage('유효한 이름을 입력하세요.');
        return;
    }

    try {
        const response = await fetch(`${API_BASE_URL}/player/update-name?name=${encodeURIComponent(newName)}`, {
            method: 'POST'
        });
        const data = await response.json();
        currentPlayer = data.player;
        updateUI();
        addSystemMessage(`이름이 ${newName}(으)로 변경되었습니다!`);
        closeSettings();
    } catch (error) {
        console.error('Error saving name:', error);
        addSystemMessage('이름 저장 오류: ' + error.message);
    }
}

async function testOllamaConnection() {
    // 브라우저가 아닌 게임 서버 기준으로 Ollama 상태를 확인 (백엔드 프록시 경유)
    const status = elements.ollamaStatus;
    status.textContent = '연결 테스트 중...';
    status.className = 'status-message';

    try {
        const response = await fetch(`${API_BASE_URL}/ollama/models`);
        const data = await response.json();
        if (response.ok && data.models && data.models.length > 0) {
            status.textContent = `Ollama 연결됨. 사용 중: ${data.current} (설치된 모델: ${data.models.join(', ')})`;
            status.className = 'status-message success';
        } else {
            status.textContent = '서버의 Ollama에 연결할 수 없습니다.';
            status.className = 'status-message error';
        }
    } catch (error) {
        status.textContent = '서버 연결 오류: ' + error.message;
        status.className = 'status-message error';
    }
}

function setupEventListeners() {
    elements.submitBtn.addEventListener('click', submitAction);
    elements.actionInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') submitAction();
    });

    elements.newGameBtn.addEventListener('click', startNewGame);
    elements.settingsBtn.addEventListener('click', openSettings);
    elements.closeSettingsBtn.addEventListener('click', closeSettings);
    elements.saveNameBtn.addEventListener('click', savePlayerName);
    elements.testOllamaBtn.addEventListener('click', testOllamaConnection);
    elements.unequipWeaponBtn.addEventListener('click', () => unequipItem('weapon'));
    elements.unequipArmorBtn.addEventListener('click', () => unequipItem('armor'));

    elements.huntBtn.addEventListener('click', startCombat);
    elements.attackBtn.addEventListener('click', () => combatAction('attack'));
    elements.skillBtn.addEventListener('click', () => combatAction('skill'));
    elements.fleeBtn.addEventListener('click', () => combatAction('flee'));
    elements.applyModelBtn.addEventListener('click', applyModel);
    elements.restBtn.addEventListener('click', restAtInn);

    elements.questBoardBtn.addEventListener('click', openQuestBoard);
    elements.closeQuestBtn.addEventListener('click', closeQuestBoard);
    elements.questModal.addEventListener('click', (e) => {
        if (e.target === elements.questModal) closeQuestBoard();
    });

    elements.shopBtn.addEventListener('click', openShop);
    elements.closeShopBtn.addEventListener('click', closeShop);
    elements.buyTabBtn.addEventListener('click', () => switchShopTab('buy'));
    elements.sellTabBtn.addEventListener('click', () => switchShopTab('sell'));

    elements.settingsModal.addEventListener('click', (e) => {
        if (e.target === elements.settingsModal) closeSettings();
    });

    elements.shopModal.addEventListener('click', (e) => {
        if (e.target === elements.shopModal) closeShop();
    });
}

function initialize() {
    setupEventListeners();
    initializeGame();
    loadLocations();
    elements.actionInput.focus();
}

document.addEventListener('DOMContentLoaded', initialize);

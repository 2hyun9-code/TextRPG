const API_BASE_URL = 'http://localhost:8000/api';

let currentPlayer = null;
let gameState = {
    isLoading: false,
    messageHistory: []
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
};

async function initializeGame() {
    try {
        const response = await fetch(`${API_BASE_URL}/game/status`);
        const data = await response.json();
        currentPlayer = data.player;

        if (!currentPlayer.job_selected) {
            await showJobSelectionModal();
        } else {
            addSystemMessage("게임이 로드되었습니다! 무엇을 하시겠습니까?");
            updateUI();
        }
    } catch (error) {
        console.error('Error loading game:', error);
        addSystemMessage('게임 로드에 실패했습니다. 백엔드 서버가 포트 8000에서 실행 중인지 확인하세요.');
    }
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
        addSystemMessage("이제 당신의 모험을 시작하세요!");
        updateUI();
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

    gameState.isLoading = true;
    elements.submitBtn.disabled = true;
    elements.actionInput.disabled = true;

    addPlayerMessage(actionText);
    elements.actionInput.value = '';

    try {
        const response = await fetch(`${API_BASE_URL}/game/action`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: actionText })
        });

        if (!response.ok) {
            const error = await response.json();
            addSystemMessage(`오류: ${error.detail}`);
            gameState.isLoading = false;
            elements.submitBtn.disabled = false;
            elements.actionInput.disabled = false;
            return;
        }

        const data = await response.json();
        currentPlayer = data.player;

        addNarratorMessage(data.narrative);

        if (data.special_event) {
            addEventMessage(data.special_event);
        }

        updateUI();
    } catch (error) {
        console.error('Error performing action:', error);
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

    const effectiveAttack = currentPlayer.equipment.weapon
        ? currentPlayer.attack + (currentPlayer.equipment.weapon.effect.attack_bonus || 0)
        : currentPlayer.attack;
    elements.playerAttack.textContent = effectiveAttack;

    const effectiveDefense = currentPlayer.equipment.armor
        ? currentPlayer.defense + (currentPlayer.equipment.armor.effect.defense_bonus || 0)
        : currentPlayer.defense;
    elements.playerDefense.textContent = effectiveDefense;

    elements.playerStrength.textContent = currentPlayer.strength;
    elements.playerDexterity.textContent = currentPlayer.dexterity;
    elements.playerIntelligence.textContent = currentPlayer.intelligence;

    updateEquipmentSlots();
    updateInventory();
    updateQuests();
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
    if (currentPlayer.quest_log.length === 0) {
        elements.questList.innerHTML = '<div class="empty-message">진행 중인 퀘스트가 없습니다</div>';
        return;
    }

    elements.questList.innerHTML = currentPlayer.quest_log
        .map(quest => `<div class="quest-item">${quest}</div>`)
        .join('');
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
    const status = elements.ollamaStatus;
    status.textContent = '연결 테스트 중...';
    status.className = 'status-message';

    try {
        const response = await fetch('http://localhost:11434/api/tags');
        if (response.ok) {
            status.textContent = 'Ollama이 실행 중이고 접근 가능합니다!';
            status.className = 'status-message success';
        } else {
            status.textContent = 'Ollama이 응답했지만 오류가 있습니다.';
            status.className = 'status-message error';
        }
    } catch (error) {
        status.textContent = `Ollama에 연결할 수 없습니다. 실행 중인지 확인하세요: 'ollama serve'`;
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

    elements.settingsModal.addEventListener('click', (e) => {
        if (e.target === elements.settingsModal) closeSettings();
    });
}

function initialize() {
    setupEventListeners();
    initializeGame();
    elements.actionInput.focus();
}

document.addEventListener('DOMContentLoaded', initialize);

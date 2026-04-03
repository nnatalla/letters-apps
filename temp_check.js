        // Ikony historii pism (globalna stała, musi być przed wszystkimi funkcjami)
        const HISTORY_ICONS = {
            'INSTYTUCJA_PUBLICZNA': '🏛️',
            'FIRMA_PRYWATNA': '🏢',
            'OSOBA_PRYWATNA': '👤',
            'WEWNETRZNE': '📁',
            'komornicze': '⚖️',
            'szkola': '🏫',
            'uczelnia': '🎓',
            'sad': '⚖️',
            'zus': '🏛️',
            'bank': '🏦',
            'default': '📄',
        };

        // Predefiniowana lista komorników - będzie ładowana z bazy danych
        let predefinedBailiffs = [];

        // Ładowanie komorników z bazy danych
        async function loadBailiffsFromDatabase() {
            try {
                const response = await fetch('/api/bailiffs');
                const result = await response.json();

                if (response.ok) {
                    predefinedBailiffs = result.bailiffs.map(bailiff => ({
                        id: bailiff.id,
                        imieNazwisko: bailiff.imie_nazwisko,
                        adres: bailiff.adres,
                        miasto: bailiff.miasto,
                        kodPocztowy: bailiff.kod_pocztowy,
                        telefon: bailiff.telefon,
                        email: bailiff.email,
                        sadRejonowy: bailiff.sad_rejonowy
                    }));
                    console.log(`📋 Załadowano ${predefinedBailiffs.length} komorników z bazy danych`);
                    console.log('Aktualna lista komorników:', predefinedBailiffs.map(b => `${b.id}: ${b.imieNazwisko}`));
                } else {
                    console.error('Błąd ładowania komorników:', result.error);
                    // Fallback do pustej listy
                    predefinedBailiffs = [];
                }
            } catch (error) {
                console.error('Błąd połączenia z bazą komorników:', error);
                predefinedBailiffs = [];
            }
        }

        let currentStep = 1;
        let selectedOption = null;
        let fileData = null;
        let additionalBailiffsCount = 0;
        let bailiffsList = [];
        let currentLetterIndex = 0;
        let allGeneratedLetters = [];
        let currentSender = null;  // wybrany nadawca pisma
        let editingSenderId = null; // id nadawcy edytowanego w modalu
        var isKomorniczeSelected = false; // checkbox komornicze - var bo używane z onclick HTML

        // File upload functionality
        const fileUpload = document.getElementById('fileUpload');
        const fileInput = document.getElementById('fileInput');

        fileUpload.addEventListener('click', () => fileInput.click());
        fileUpload.addEventListener('dragover', (e) => {
            e.preventDefault();
            fileUpload.classList.add('dragover');
        });
        fileUpload.addEventListener('dragleave', () => {
            fileUpload.classList.remove('dragover');
        });
        fileUpload.addEventListener('drop', (e) => {
            e.preventDefault();
            fileUpload.classList.remove('dragover');
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                handleFile(files[0]);
            }
        });

        fileInput.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                handleFile(e.target.files[0]);
            }
        });

        // Checkbox komornicze — przełącza tryb
        document.getElementById('isKomorniczeCheck').addEventListener('change', function() {
            isKomorniczeSelected = this.checked;
            const step3ind = document.getElementById('step-indicator-3');
            if (step3ind) step3ind.style.display = isKomorniczeSelected ? '' : 'none';
            const btn = document.getElementById('step2NextBtn');
            if (btn) btn.textContent = isKomorniczeSelected ? 'Przejdź do weryfikacji' : 'Generuj List ▶';
        });

        // Init: domyślnie tryb universal (checkbox niezaznaczony) — ukryj krok 3
        document.getElementById('step-indicator-3').style.display = 'none';
        document.getElementById('step2NextBtn').textContent = 'Generuj List ▶';

        function handleFile(file) {
            fileData = file;
            document.getElementById('fileName').textContent = `✅ Wybrano plik: ${file.name}`;
        }

        async function processFile() {
            if (!fileData) {
                showToast('Wybierz plik!', 'warning');
                return;
            }

            // Sprawdź rozmiar pliku (max 10 MB)
            if (fileData.size > 10 * 1024 * 1024) {
                showToast('Plik jest za duży. Maksymalny rozmiar to 10 MB.', 'error');
                return;
            }

            // Pokaż loading overlay i zablokuj przycisk
            showLoadingOverlay();
            document.querySelector('.btn').textContent = 'Przetwarzam...';
            document.querySelector('.btn').disabled = true;

            const formData = new FormData();
            formData.append('file', fileData);

            try {
                const response = await fetch('/process-file', {
                    method: 'POST',
                    body: formData
                });

                const result = await response.json();

                if (!response.ok) {
                    hideLoadingOverlay();
                    document.querySelector('.btn').textContent = 'Przetwórz Pismo';
                    document.querySelector('.btn').disabled = false;
                    showToast('Błąd wysyłania pliku: ' + (result.error || 'Nieznany błąd'), 'error');
                    return;
                }

                if (result.task_id) {
                    // Serwer zwrócił task_id – startujemy polling (Celery async)
                    pollTaskStatus(result.task_id);
                } else if (result.result) {
                    // Synchroniczny fallback – wynik bezpośrednio (bez Redis)
                    hideLoadingOverlay();
                    document.querySelector('.btn').textContent = 'Przetwórz Pismo';
                    document.querySelector('.btn').disabled = false;
                    const r = result.result;
                    populateOCRResults(r.dane, r.mode, r.classification, r.fields, r.summary);
                    goToStep(2);
                    loadSenders();
                    showToast('Pismo przetworzone pomyślnie!', 'success');
                } else {
                    hideLoadingOverlay();
                    document.querySelector('.btn').textContent = 'Przetwórz Pismo';
                    document.querySelector('.btn').disabled = false;
                    showToast('Nieoczekiwana odpowiedź serwera.', 'error');
                }

            } catch (error) {
                console.error('Błąd połączenia z serwerem:', error);
                hideLoadingOverlay();
                document.querySelector('.btn').textContent = 'Przetwórz Pismo';
                document.querySelector('.btn').disabled = false;
                showToast('Nie udało się połączyć z serwerem.', 'error');
            }
        }

        function pollTaskStatus(taskId) {
            const interval = setInterval(async () => {
                try {
                    const resp = await fetch('/task-status/' + taskId);
                    const data = await resp.json();

                    if (data.status === 'SUCCESS') {
                        clearInterval(interval);
                        hideLoadingOverlay();
                        document.querySelector('.btn').textContent = 'Przetwórz Pismo';
                        document.querySelector('.btn').disabled = false;
                        const result = data.result;
                        populateOCRResults(
                            result.dane,
                            result.mode,
                            result.classification,
                            result.fields,
                            result.summary
                        );
                        goToStep(2);
                        loadSenders();
                        showToast('Pismo przetworzone pomyślnie!', 'success');

                    } else if (data.status === 'FAILURE') {
                        clearInterval(interval);
                        hideLoadingOverlay();
                        document.querySelector('.btn').textContent = 'Przetwórz Pismo';
                        document.querySelector('.btn').disabled = false;
                        showToast('Błąd przetwarzania: ' + (data.error || 'Nieznany błąd'), 'error');

                    } else if (data.error) {
                        clearInterval(interval);
                        hideLoadingOverlay();
                        document.querySelector('.btn').textContent = 'Przetwórz Pismo';
                        document.querySelector('.btn').disabled = false;
                        showToast('Błąd: ' + data.error, 'error');
                    }
                    // PENDING / STARTED – czekamy na kolejne odpytanie
                } catch (e) {
                    clearInterval(interval);
                    hideLoadingOverlay();
                    document.querySelector('.btn').textContent = 'Przetwórz Pismo';
                    document.querySelector('.btn').disabled = false;
                    showToast('Błąd połączenia podczas sprawdzania statusu.', 'error');
                }
            }, 2000);
        }

        function populateOCRResults(data, mode, classification, fields, summary) {
            // Checkbox komornicze nadpisuje tryb — użytkownik decyduje o ścieżce
            if (isKomorniczeSelected) {
                mode = 'komornicze';
                // Bezpieczne domyślne struktury gdy AI nie wykryło komornicze
                data = data || {};
                data.komornik = data.komornik || { imieNazwisko: '', adres: '', miasto: '', telefon: '', email: '' };
                data.dluznik  = data.dluznik  || { imieNazwisko: '', pesel: '' };
                data.sprawa   = data.sprawa   || { sygnaturaSprawy: '', numerRachunku: '' };
            }
    // TRYB KOMORNICZY - stara logika bez zmian
        if (mode === 'komornicze') {
            document.getElementById('bailiffName').textContent = data.komornik.imieNazwisko || '';
            document.getElementById('bailiffAddress').textContent = data.komornik.adres || '';
            document.getElementById('bailiffCity').textContent = data.komornik.miasto || '';
            document.getElementById('bailiffContact').textContent =
                `${data.komornik.telefon || ''} ${data.komornik.email || ''}`.trim();
            document.getElementById('debtorName').textContent = data.dluznik.imieNazwisko || '';
            document.getElementById('debtorPesel').textContent = data.dluznik.pesel || '';
            document.getElementById('caseNumber').textContent = data.sprawa.sygnaturaSprawy || '';
            document.getElementById('bankAccount').textContent = data.sprawa.numerRachunku || '';

            document.getElementById('editBailiffName').value = data.komornik.imieNazwisko || '';
            document.getElementById('editBailiffAddress').value = data.komornik.adres || '';
            document.getElementById('editBailiffCity').value = data.komornik.miasto || '';
            document.getElementById('editBailiffContact').value =
                `${data.komornik.telefon || ''} ${data.komornik.email || ''}`.trim();
            document.getElementById('editDebtorName').value = data.dluznik.imieNazwisko || '';
            document.getElementById('editDebtorPesel').value = data.dluznik.pesel || '';
            document.getElementById('editCaseNumber').value = data.sprawa.sygnaturaSprawy || '';
            document.getElementById('editBankAccount').value = data.sprawa.numerRachunku || '';

            const pesel = data.dluznik.pesel;
            if (pesel && pesel.length >= 10) {
                searchEmployeeInDatabase(pesel);
            }

            // Pokaż standardowy krok 2
            document.getElementById('step2-komornicze').style.display = 'block';
            document.getElementById('step2-universal').style.display = 'none';
            // Zapisz dla ewentualnego powrotu
            window.currentClassification = classification || { is_komornicze: true, category: 'INSTYTUCJA_PUBLICZNA', subtype: 'komornik' };
            window.currentFields = [];
            return;
        }

        // TRYB UNIWERSALNY - dynamiczne pola
        document.getElementById('step2-komornicze').style.display = 'none';
        document.getElementById('step2-universal').style.display = 'block';

        // Pokaż badge z typem pisma
        const classDiv = document.getElementById('universal-classification');
        const confidence = Math.round((classification.confidence || 0) * 100);
        classDiv.innerHTML = `
            <div style="background: linear-gradient(135deg, #1e3c72, #2a5298); color: white;
                        padding: 15px 20px; border-radius: 10px; margin-bottom: 20px;">
                <strong>📄 Typ pisma:</strong> ${classification.subtype || 'nieznany'}
                &nbsp;&nbsp;|&nbsp;&nbsp;
                <strong>Kategoria:</strong> ${classification.category || ''}
                &nbsp;&nbsp;|&nbsp;&nbsp;
                <strong>Pewność:</strong> ${confidence}%
                ${summary ? `<br><small style="opacity:0.85; margin-top:8px; display:block;">💬 ${summary}</small>` : ''}
            </div>`;

        // Zapisz dane klasyfikacji globalnie (potrzebne przy generowaniu)
        window.currentClassification = classification;
        window.currentFields = fields;

        // Renderuj pola dynamicznie
        const fieldsContainer = document.getElementById('universal-fields-grid');
        fieldsContainer.innerHTML = '';

        (fields || []).forEach(field => {
            const div = document.createElement('div');
            div.className = 'form-group';
            div.innerHTML = `
                <label for="ufield_${field.id}">
                    ${field.label}
                    ${field.required ? '<span style="color:#e53e3e">*</span>' : ''}
                    <small style="color:#888; font-weight:normal;">(${field.type})</small>
                </label>
                <div style="display:flex; gap:8px; align-items:center;">
                    <input type="text" id="ufield_${field.id}"
                        value="${field.value || ''}"
                        placeholder="${field.value ? '' : 'Nie rozpoznano - uzupełnij ręcznie'}"
                        style="${!field.value ? 'border-color:#e2a000;' : ''}">
                    <button type="button" onclick="copyFieldValue('ufield_${field.id}')"
                            style="background:#edf2f7; border:1px solid #cbd5e0; border-radius:8px;
                                padding:10px; cursor:pointer; white-space:nowrap;">📋</button>
                </div>`;
            fieldsContainer.appendChild(div);
        });
    }

function copyFieldValue(inputId) {
    const val = document.getElementById(inputId).value;
    if (val) navigator.clipboard.writeText(val).catch(() => {});
}
        function copyToClipboard(elementId) {
            const element = document.getElementById(elementId);
            const text = element.textContent;
            navigator.clipboard.writeText(text).then(() => {
                const button = element.parentNode.querySelector('.copy-btn');
                const originalText = button.textContent;
                button.textContent = '✅';
                button.style.background = 'rgba(40, 167, 69, 0.8)';

                setTimeout(() => {
                    button.textContent = originalText;
                    button.style.background = 'rgba(255,255,255,0.2)';
                }, 2000);
            }).catch(err => {
                console.error('Błąd kopiowania: ', err);
                alert('Nie udało się skopiować tekstu');
            });
        }

        function goToStep(step) {
            document.querySelectorAll('.step').forEach(s => s.classList.remove('active'));
            document.querySelectorAll('.step-item').forEach(s => s.classList.remove('active', 'completed'));

            document.getElementById(`step-${step}`).classList.add('active');
            currentStep = step;

            for (let i = 1; i <= 4; i++) {
                const stepItem = document.querySelector(`[data-step="${i}"]`);
                if (i < step) {
                    stepItem.classList.add('completed');
                } else if (i === step) {
                    stepItem.classList.add('active');
                }
            }

            const progress = (step / 4) * 100;
            document.querySelector('.progress-fill').style.width = progress + '%';
        }

        function selectOption(option) {
            selectedOption = option;

            document.querySelectorAll('.radio-option').forEach(opt => opt.classList.remove('selected'));
            document.querySelectorAll('input[name="verification"]').forEach(input => input.checked = false);

            document.getElementById(`option${option}`).checked = true;
            document.querySelector(`[onclick="selectOption(${option})"]`).classList.add('selected');

            for (let i = 1; i <= 4; i++) {
                const fields = document.getElementById(`additionalFields${i}`);
                if (fields) {
                    fields.style.display = (i === option) ? 'block' : 'none';
                }
            }

            if (option === 4) {
                populateZbiegData();
            }
        }

        function populateZbiegData() {
            const companyName = currentSender ? currentSender.nazwa : '';
            const today = new Date().toISOString().split('T')[0];

            document.getElementById('zbiegCompany').value = companyName;
            document.getElementById('zbiegDate').value = today;
            document.getElementById('zbiegDebtorName').value = document.getElementById('editDebtorName').value;
            document.getElementById('zbiegDebtorPesel').value = document.getElementById('editDebtorPesel').value;
            document.getElementById('zbiegBailiffA_Name').value = document.getElementById('editBailiffName').value;
            document.getElementById('zbiegBailiffA_Case').value = document.getElementById('editCaseNumber').value;
            document.getElementById('zbiegBailiffA_Address').value = document.getElementById('editBailiffAddress').value;
            document.getElementById('zbiegBailiffA_City').value = document.getElementById('editBailiffCity').value;
        }

        function addBailiff() {
            additionalBailiffsCount++;
            const container = document.getElementById('additionalBailiffs');

            const bailiffDiv = document.createElement('div');
            bailiffDiv.className = 'bailiff-entry';
            bailiffDiv.innerHTML = `
                <h4>
                    Komornik ${String.fromCharCode(65 + additionalBailiffsCount)}
                    <button type="button" class="remove-bailiff" onclick="removeBailiff(this)">Usuń</button>
                </h4>
                
                <div class="form-group bailiff-buttons-group" id="bailiffButtons${additionalBailiffsCount}" style="margin-bottom: 15px;">
                    <div style="display: flex; gap: 10px;">
                        <button type="button" class="btn-secondary btn btn-small" onclick="openBailiffSelector(${additionalBailiffsCount})" style="flex: 1;">
                            📋 Wybierz komornika z listy
                        </button>
                        <button type="button" class="btn btn-small" onclick="openAddBailiffForm()" style="flex: 1; background: #28a745; color: white;">
                            ➕ Dodaj nowego komornika
                        </button>
                    </div>
                </div>
                
                <div class="bailiff-grid">
                    <div class="form-group">
                        <label>Imię i Nazwisko:</label>
                        <input type="text" name="additionalBailiffName${additionalBailiffsCount}" required onchange="updateBailiffSummary()">
                    </div>
                    <div class="form-group">
                        <label>Numer sprawy:</label>
                        <input type="text" name="additionalBailiffCase${additionalBailiffsCount}" required onchange="updateBailiffSummary()">
                    </div>
                    <div class="form-group">
                        <label>Ulica:</label>
                        <input type="text" name="additionalBailiffAddress${additionalBailiffsCount}" required onchange="updateBailiffSummary()">
                    </div>
                    <div class="form-group">
                        <label>Kod pocztowy i miasto:</label>
                        <input type="text" name="additionalBailiffCity${additionalBailiffsCount}" required onchange="updateBailiffSummary()">
                    </div>
                </div>
                <div class="form-group">
                    <label>Data wpłynięcia pisma tego komornika:</label>
                    <input type="date" name="additionalBailiffDate${additionalBailiffsCount}" required onchange="updateBailiffSummary()">
                </div>
            `;

            container.appendChild(bailiffDiv);
            updateBailiffSummary();
        }

        function removeBailiff(button) {
            button.parentNode.parentNode.remove();
            updateBailiffSummary();
        }

        // Wrapper function dla onclick w HTML
        function openBailiffSelector(bailiffIndex) {
            showBailiffSelector(bailiffIndex);
        }

        async function showBailiffSelector(bailiffIndex) {
            // Zapisz globalnie indeks formularza dla którego otwieramy modal
            window.currentBailiffSelectorIndex = bailiffIndex;

            // Najpierw odśwież listę komorników z bazy danych
            await loadBailiffsFromDatabase();

            // Tworzymy modal z listą komorników
            const modal = document.createElement('div');
            modal.className = 'bailiff-selector-modal';
            modal.style.cssText = `
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: rgba(0,0,0,0.5);
                display: flex;
                justify-content: center;
                align-items: center;
                z-index: 1000;
            `;

            const modalContent = document.createElement('div');
            modalContent.style.cssText = `
                background: white;
                padding: 30px;
                border-radius: 15px;
                max-width: 600px;
                width: 90%;
                height: 70vh;
                display: flex;
                flex-direction: column;
                box-shadow: 0 20px 40px rgba(0,0,0,0.3);
            `;

            modalContent.innerHTML = `
                <h3 style="margin-bottom: 20px; color: #2a5298; flex-shrink: 0;">Wybierz komornika z listy</h3>
                <div class="bailiff-list" style="
                    flex: 1;
                    overflow-y: auto;
                    padding-right: 10px;
                    margin-bottom: 20px;
                ">
                    ${predefinedBailiffs.map((bailiff, index) => `
                        <div class="bailiff-option" style="
                            padding: 15px;
                            border: 2px solid #cbd5e0;
                            border-radius: 10px;
                            margin-bottom: 10px;
                            transition: all 0.3s ease;
                            display: flex;
                            justify-content: space-between;
                            align-items: center;
                        " onmouseover="this.style.borderColor='#2a5298'; this.style.background='#e6f2ff';" 
                           onmouseout="this.style.borderColor='#cbd5e0'; this.style.background='white';">
                            <div onclick="selectBailiff(${index}, ${bailiffIndex})" style="flex: 1; cursor: pointer;">
                                <strong>${bailiff.imieNazwisko}</strong><br>
                                <small style="color: #666;">${bailiff.adres}, ${bailiff.kodPocztowy} ${bailiff.miasto}</small>
                            </div>
                            <div style="display: flex; gap: 5px;">
                                <button onclick="editBailiff(${bailiff.id}, event)" style="
                                    background: #28a745;
                                    color: white;
                                    border: none;
                                    padding: 8px 12px;
                                    border-radius: 6px;
                                    cursor: pointer;
                                    font-size: 12px;
                                " title="Edytuj komornika">✏️ Edytuj</button>
                                <button onclick="confirmDeleteBailiff(${bailiff.id}, '${bailiff.imieNazwisko}', event)" style="
                                    background: #dc3545;
                                    color: white;
                                    border: none;
                                    padding: 8px 12px;
                                    border-radius: 6px;
                                    cursor: pointer;
                                    font-size: 12px;
                                " title="Usuń komornika">🗑️ Usuń</button>
                            </div>
                        </div>
                    `).join('')}
                </div>
                <button onclick="closeBailiffSelector()" style="
                    width: 100%;
                    padding: 12px;
                    background: #6c757d;
                    color: white;
                    border: none;
                    border-radius: 8px;
                    cursor: pointer;
                    flex-shrink: 0;
                ">Wyjdź</button>
            `;

            modal.appendChild(modalContent);
            document.body.appendChild(modal);

            // Zamykanie na kliknięcie tła
            modal.addEventListener('click', (e) => {
                if (e.target === modal) {
                    closeBailiffSelector();
                }
            });
        }

        function selectBailiff(bailiffIndex, formIndex) {
            const selectedBailiff = predefinedBailiffs[bailiffIndex];

            // Uzupełniamy pola formularza
            document.querySelector(`input[name="additionalBailiffName${formIndex}"]`).value = selectedBailiff.imieNazwisko;
            document.querySelector(`input[name="additionalBailiffAddress${formIndex}"]`).value = selectedBailiff.adres;
            document.querySelector(`input[name="additionalBailiffCity${formIndex}"]`).value = `${selectedBailiff.kodPocztowy} ${selectedBailiff.miasto}`;

            // Ukryj przyciski i pokaż informację o automatycznym uzupełnieniu
            hideButtonsAndShowAutoFilledNotice(formIndex, selectedBailiff.imieNazwisko);

            closeBailiffSelector();
            updateBailiffSummary();

            // Pokazujemy komunikat o uzupełnieniu
            const notification = document.createElement('div');
            notification.style.cssText = `
                position: fixed;
                top: 20px;
                right: 20px;
                background: #28a745;
                color: white;
                padding: 15px 20px;
                border-radius: 8px;
                z-index: 1001;
                box-shadow: 0 5px 15px rgba(0,0,0,0.2);
            `;
            notification.textContent = `Dane komornika ${selectedBailiff.imieNazwisko} zostały uzupełnione!`;
            document.body.appendChild(notification);

            setTimeout(() => {
                notification.remove();
            }, 3000);
        }

        function closeBailiffSelector() {
            const modal = document.querySelector('.bailiff-selector-modal');
            if (modal) {
                modal.remove();
            }
            // Wyczyść zmienną globalną
            window.currentBailiffSelectorIndex = null;
        }

        function confirmDeleteBailiff(bailiffId, bailiffName, event) {
            // Zatrzymaj propagację eventu, żeby nie wybierać komornika
            event.stopPropagation();

            // Utwórz modal potwierdzenia
            const confirmModal = document.createElement('div');
            confirmModal.className = 'delete-confirm-modal';
            confirmModal.style.cssText = `
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: rgba(0,0,0,0.6);
                display: flex;
                justify-content: center;
                align-items: center;
                z-index: 1001;
            `;

            const confirmContent = document.createElement('div');
            confirmContent.style.cssText = `
                background: white;
                padding: 30px;
                border-radius: 15px;
                max-width: 500px;
                width: 90%;
                box-shadow: 0 20px 40px rgba(0,0,0,0.3);
                text-align: center;
            `;

            confirmContent.innerHTML = `
                <h3 style="color: #dc3545; margin-bottom: 20px;">⚠️ Usunięcie komornika</h3>
                <p style="margin-bottom: 20px; color: #333;">
                    Czy na pewno chcesz usunąć komornika:<br>
                    <strong>${bailiffName}</strong>?
                </p>
                <p style="margin-bottom: 20px; color: #666; font-size: 14px;">
                    Aby potwierdzić usunięcie, wpisz dokładnie słowo: <strong>potwierdzam</strong>
                </p>
                <input type="text" id="deleteConfirmation" placeholder="Wpisz: potwierdzam" style="
                    width: 100%;
                    padding: 12px;
                    border: 2px solid #cbd5e0;
                    border-radius: 8px;
                    margin-bottom: 20px;
                    box-sizing: border-box;
                    text-align: center;
                    font-size: 16px;
                ">
                <div style="display: flex; gap: 10px; justify-content: center;">
                    <button onclick="closeDeleteModal()" style="
                        padding: 12px 24px;
                        background: #6c757d;
                        color: white;
                        border: none;
                        border-radius: 8px;
                        cursor: pointer;
                        font-size: 14px;
                    ">Anuluj</button>
                    <button onclick="executeBailiffDeletion(${bailiffId}, '${bailiffName}')" style="
                        padding: 12px 24px;
                        background: #dc3545;
                        color: white;
                        border: none;
                        border-radius: 8px;
                        cursor: pointer;
                        font-size: 14px;
                    ">Usuń komornika</button>
                </div>
            `;

            confirmModal.appendChild(confirmContent);
            document.body.appendChild(confirmModal);

            // Focus na pole tekstowe
            setTimeout(() => {
                document.getElementById('deleteConfirmation').focus();
            }, 100);
        }

        function closeDeleteModal() {
            const modal = document.querySelector('.delete-confirm-modal');
            if (modal) {
                modal.remove();
            }
        }

        async function executeBailiffDeletion(bailiffId, bailiffName) {
            const confirmation = document.getElementById('deleteConfirmation').value.trim();

            if (confirmation !== 'potwierdzam') {
                alert('Nieprawidłowe potwierdzenie. Wpisz dokładnie słowo "potwierdzam"');
                return;
            }

            try {
                const response = await fetch('/api/delete-bailiff', {
                    method: 'DELETE',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        bailiff_id: bailiffId,
                        confirmation: confirmation
                    })
                });

                const result = await response.json();

                if (response.ok) {
                    // Zamknij modal potwierdzenia
                    closeDeleteModal();

                    // Zamknij modal wyboru komornika
                    closeBailiffSelector();

                    // Przeładuj listę komorników
                    await loadBailiffsFromDatabase();

                    // Pokaż powiadomienie o sukcesie
                    showEmployeeSearchStatus(`✅ ${result.message}`, 'success');
                } else {
                    alert(`Błąd: ${result.error}`);
                }
            } catch (error) {
                console.error('Błąd usuwania komornika:', error);
                alert('Wystąpił błąd podczas usuwania komornika');
            }
        }

        async function editBailiff(bailiffId, event) {
            event.stopPropagation();

            console.log('🔧 editBailiff wywołane z bailiffId:', bailiffId, 'typ:', typeof bailiffId);

            try {
                // Pobierz aktualne dane komornika
                const response = await fetch('/api/bailiffs');
                const data = await response.json();
                console.log('🔧 Wszystkie komornicy z API:', data.bailiffs.map(b => `${b.id}: ${b.imie_nazwisko}`));
                console.log('🔧 Szukam komornika o ID:', bailiffId);
                const bailiff = data.bailiffs.find(b => b.id === bailiffId);
                console.log('🔧 Znaleziony komornik:', bailiff);
                console.log('🔧 bailiff.imie_nazwisko:', bailiff.imie_nazwisko);
                console.log('🔧 bailiff.plec:', bailiff.plec);
                console.log('🔧 bailiff.adres:', bailiff.adres);

                if (!bailiff) {
                    console.error('🚨 Nie znaleziono komornika o ID:', bailiffId);
                    alert('Nie znaleziono komornika');
                    return;
                }

                // Utwórz modal edycji
                const editModal = document.createElement('div');
                editModal.className = 'edit-bailiff-modal';
                editModal.innerHTML = `
                    <div style="
                        position: fixed;
                        top: 0;
                        left: 0;
                        width: 100%;
                        height: 100%;
                        background: rgba(0,0,0,0.5);
                        display: flex;
                        justify-content: center;
                        align-items: center;
                        z-index: 10000;
                    ">
                        <div style="
                            background: white;
                            padding: 30px;
                            border-radius: 15px;
                            max-width: 500px;
                            width: 90%;
                            max-height: 90vh;
                            overflow-y: auto;
                            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
                        ">
                            <h3 style="margin: 0 0 20px 0; color: #2a5298; text-align: center;">
                                ✏️ Edycja danych komornika
                            </h3>
                            
                            <form id="editBailiffForm">
                                <div style="margin-bottom: 15px;">
                                    <label style="display: block; margin-bottom: 5px; font-weight: bold; color: #333;">
                                        Imię i nazwisko *:
                                    </label>
                                    <input type="text" id="modalEditBailiffName" value="${bailiff.imie_nazwisko}" style="
                                        width: 100%;
                                        padding: 10px;
                                        border: 2px solid #cbd5e0;
                                        border-radius: 8px;
                                        font-size: 14px;
                                        box-sizing: border-box;
                                    " required>
                                </div>
                                
                                <div style="margin-bottom: 15px;">
                                    <label style="display: block; margin-bottom: 5px; font-weight: bold; color: #333;">
                                        Płeć *:
                                    </label>
                                    <select id="modalEditBailiffGender" style="
                                        width: 100%;
                                        padding: 10px;
                                        border: 2px solid #cbd5e0;
                                        border-radius: 8px;
                                        font-size: 14px;
                                        box-sizing: border-box;
                                    " required>
                                        <option value="m" ${bailiff.plec === 'm' ? 'selected' : ''}>Mężczyzna</option>
                                        <option value="k" ${bailiff.plec === 'k' ? 'selected' : ''}>Kobieta</option>
                                    </select>
                                </div>
                                
                                <div style="margin-bottom: 15px;">
                                    <label style="display: block; margin-bottom: 5px; font-weight: bold; color: #333;">
                                        Adres *:
                                    </label>
                                    <input type="text" id="modalEditBailiffAddress" value="${bailiff.adres}" style="
                                        width: 100%;
                                        padding: 10px;
                                        border: 2px solid #cbd5e0;
                                        border-radius: 8px;
                                        font-size: 14px;
                                        box-sizing: border-box;
                                    " required>
                                </div>
                                
                                <div style="display: flex; gap: 10px; margin-bottom: 15px;">
                                    <div style="flex: 1;">
                                        <label style="display: block; margin-bottom: 5px; font-weight: bold; color: #333;">
                                            Kod pocztowy *:
                                        </label>
                                        <input type="text" id="modalEditBailiffPostalCode" value="${bailiff.kod_pocztowy}" style="
                                            width: 100%;
                                            padding: 10px;
                                            border: 2px solid #cbd5e0;
                                            border-radius: 8px;
                                            font-size: 14px;
                                            box-sizing: border-box;
                                        " required>
                                    </div>
                                    <div style="flex: 2;">
                                        <label style="display: block; margin-bottom: 5px; font-weight: bold; color: #333;">
                                            Miasto *:
                                        </label>
                                        <input type="text" id="modalEditBailiffCity" value="${bailiff.miasto}" style="
                                            width: 100%;
                                            padding: 10px;
                                            border: 2px solid #cbd5e0;
                                            border-radius: 8px;
                                            font-size: 14px;
                                            box-sizing: border-box;
                                        " required>
                                    </div>
                                </div>
                                
                                <div style="margin-bottom: 15px;">
                                    <label style="display: block; margin-bottom: 5px; font-weight: bold; color: #333;">
                                        Telefon:
                                    </label>
                                    <input type="text" id="modalEditBailiffPhone" value="${bailiff.telefon || ''}" style="
                                        width: 100%;
                                        padding: 10px;
                                        border: 2px solid #cbd5e0;
                                        border-radius: 8px;
                                        font-size: 14px;
                                        box-sizing: border-box;
                                    ">
                                </div>
                                
                                <div style="margin-bottom: 15px;">
                                    <label style="display: block; margin-bottom: 5px; font-weight: bold; color: #333;">
                                        Email:
                                    </label>
                                    <input type="email" id="modalEditBailiffEmail" value="${bailiff.email || ''}" style="
                                        width: 100%;
                                        padding: 10px;
                                        border: 2px solid #cbd5e0;
                                        border-radius: 8px;
                                        font-size: 14px;
                                        box-sizing: border-box;
                                    ">
                                </div>
                                
                                <div style="margin-bottom: 20px;">
                                    <label style="display: block; margin-bottom: 5px; font-weight: bold; color: #333;">
                                        Sąd rejonowy:
                                    </label>
                                    <input type="text" id="modalEditBailiffCourt" value="${bailiff.sad_rejonowy || ''}" style="
                                        width: 100%;
                                        padding: 10px;
                                        border: 2px solid #cbd5e0;
                                        border-radius: 8px;
                                        font-size: 14px;
                                        box-sizing: border-box;
                                    ">
                                </div>
                                
                                <div style="display: flex; gap: 10px; justify-content: center;">
                                    <button type="button" onclick="closeEditModal()" style="
                                        flex: 1;
                                        padding: 12px;
                                        background: #6c757d;
                                        color: white;
                                        border: none;
                                        border-radius: 8px;
                                        cursor: pointer;
                                        font-weight: bold;
                                        transition: all 0.3s ease;
                                    ">Anuluj</button>
                                    <button type="button" onclick="executeBailiffUpdate(` + bailiffId + `)" style="
                                        flex: 1;
                                        padding: 12px;
                                        background: #28a745;
                                        color: white;
                                        border: none;
                                        border-radius: 8px;
                                        cursor: pointer;
                                        font-weight: bold;
                                        transition: all 0.3s ease;
                                    ">Zapisz zmiany</button>
                                </div>
                            </form>
                        </div>
                    </div>
                `;

                document.body.appendChild(editModal);

                // Debug: sprawdź czy wartości zostały poprawnie wstawione
                setTimeout(() => {
                    const nameField = document.getElementById('modalEditBailiffName');
                    const genderField = document.getElementById('modalEditBailiffGender');
                    const addressField = document.getElementById('modalEditBailiffAddress');
                    console.log('🔧 Wartość w polu nazwa po utworzeniu modalu:', nameField ? nameField.value : 'POLE NIE ISTNIEJE');
                    console.log('🔧 Wartość w polu płeć po utworzeniu modalu:', genderField ? genderField.value : 'POLE NIE ISTNIEJE');
                    console.log('🔧 Wartość w polu adres po utworzeniu modalu:', addressField ? addressField.value : 'POLE NIE ISTNIEJE');
                }, 100);

                // Focus na pierwsze pole
                setTimeout(() => {
                    document.getElementById('modalEditBailiffName').focus();
                }, 100);

                // Obsługa klawisza Enter w formularzu
                const form = document.getElementById('editBailiffForm');
                form.addEventListener('keydown', function (event) {
                    if (event.key === 'Enter') {
                        event.preventDefault(); // Zapobiega domyślnej akcji formularza
                        console.log('🔧 Naciśnięto Enter - zapisuję zmiany');
                        executeBailiffUpdate(bailiffId);
                    } else if (event.key === 'Escape') {
                        event.preventDefault();
                        console.log('🔧 Naciśnięto Escape - zamykam modal');
                        closeEditModal();
                    }
                });

                // Globalna obsługa Escape dla całego dokumentu
                const escapeHandler = function (event) {
                    if (event.key === 'Escape') {
                        const modal = document.querySelector('.edit-bailiff-modal');
                        if (modal) {
                            console.log('🔧 Globalny Escape - zamykam modal');
                            closeEditModal();
                        }
                    }
                };

                // Rejestruj handler i zapisz do późniejszego usunięcia
                if (!document._bailiffEscapeHandlers) {
                    document._bailiffEscapeHandlers = [];
                }
                document._bailiffEscapeHandlers.push(escapeHandler);
                document.addEventListener('keydown', escapeHandler);

            } catch (error) {
                console.error('Błąd podczas otwierania edycji:', error);
                alert('Wystąpił błąd podczas otwierania formularza edycji');
            }
        }

        function closeEditModal() {
            const modal = document.querySelector('.edit-bailiff-modal');
            if (modal) {
                // Usuń globalne event listenery
                const existingHandlers = document._bailiffEscapeHandlers || [];
                existingHandlers.forEach(handler => {
                    document.removeEventListener('keydown', handler);
                });
                document._bailiffEscapeHandlers = [];

                modal.remove();
            }
        }

        async function executeBailiffUpdate(bailiffId) {
            console.log('🔧 executeBailiffUpdate wywołane z bailiffId:', bailiffId, 'typ:', typeof bailiffId);

            const name = document.getElementById('modalEditBailiffName').value.trim();
            const gender = document.getElementById('modalEditBailiffGender').value;
            const address = document.getElementById('modalEditBailiffAddress').value.trim();
            const postalCode = document.getElementById('modalEditBailiffPostalCode').value.trim();
            const city = document.getElementById('modalEditBailiffCity').value.trim();
            const phone = document.getElementById('modalEditBailiffPhone').value.trim();
            const email = document.getElementById('modalEditBailiffEmail').value.trim();
            const court = document.getElementById('modalEditBailiffCourt').value.trim();

            console.log('🔧 Dane do wysłania:', {
                bailiff_id: bailiffId,
                imie_nazwisko: name,
                plec: gender,
                adres: address,
                kod_pocztowy: postalCode,
                miasto: city,
                telefon: phone,
                email: email,
                sad_rejonowy: court
            });

            // Walidacja wymaganych pól
            console.log('🔧 Sprawdzam walidację pól:');
            console.log('🔧 name:', name, 'długość:', name.length);
            console.log('🔧 gender:', gender);
            console.log('🔧 address:', address, 'długość:', address.length);
            console.log('🔧 postalCode:', postalCode, 'długość:', postalCode.length);
            console.log('🔧 city:', city, 'długość:', city.length);

            if (!name || !gender || !address || !postalCode || !city) {
                console.error('🚨 Walidacja nie przeszła!');
                alert('Wszystkie pola oznaczone * są wymagane');
                return;
            }

            console.log('✅ Walidacja przeszła, wysyłam request...');

            try {
                console.log('🌐 Rozpoczynam fetch do /api/update-bailiff');
                console.log('🌐 Current URL:', window.location.href);
                console.log('🌐 Fetch URL będzie:', new URL('/api/update-bailiff', window.location.href).href);

                const response = await fetch('/api/update-bailiff', {
                    method: 'PUT',
                    headers: {
                        'Content-Type': 'application/json',
                        'Cache-Control': 'no-cache',
                        'Pragma': 'no-cache'
                    },
                    cache: 'no-cache',
                    body: JSON.stringify({
                        bailiff_id: bailiffId,
                        imie_nazwisko: name,
                        plec: gender,
                        adres: address,
                        kod_pocztowy: postalCode,
                        miasto: city,
                        telefon: phone,
                        email: email,
                        sad_rejonowy: court,
                        timestamp: Date.now()
                    })
                });

                console.log('🌐 Otrzymałem response:', response);
                console.log('🌐 Response status:', response.status);
                console.log('🌐 Response ok:', response.ok);

                const result = await response.json();
                console.log('🌐 Response JSON:', result);

                if (response.ok) {
                    console.log('Sukces aktualizacji komornika:', result);

                    // Zamknij modal edycji
                    closeEditModal();

                    // Przeładuj listę komorników
                    await loadBailiffsFromDatabase();

                    // Sprawdź czy edytowany komornik jest aktualnie używany w jakimś formularzu
                    // i jeśli tak, zaktualizuj dane w formularzu
                    updateFormularzeWithEditedBailiff(bailiffId, result.bailiff);

                    // Sprawdź czy modal wyboru komornika jest otwarty
                    const selectorModal = document.querySelector('.bailiff-selector-modal');
                    if (selectorModal) {
                        console.log('Modal jest otwarty, odświeżam jego zawartość');
                        // Zamiast zamykać modal, odśwież jego zawartość
                        const bailiffList = selectorModal.querySelector('.bailiff-list');
                        if (bailiffList) {
                            // Znajdź bailiffIndex z onclick handlera
                            const currentBailiffIndex = window.currentBailiffSelectorIndex || 0;

                            // Wygeneruj nową listę HTML
                            bailiffList.innerHTML = predefinedBailiffs.map((bailiff, index) => `
                                <div class="bailiff-option" style="
                                    padding: 15px;
                                    border: 2px solid #cbd5e0;
                                    border-radius: 10px;
                                    margin-bottom: 10px;
                                    transition: all 0.3s ease;
                                    display: flex;
                                    justify-content: space-between;
                                    align-items: center;
                                " onmouseover="this.style.borderColor='#2a5298'; this.style.background='#e6f2ff';" 
                                   onmouseout="this.style.borderColor='#cbd5e0'; this.style.background='white';">
                                    <div onclick="selectBailiff(${index}, ${currentBailiffIndex})" style="flex: 1; cursor: pointer;">
                                        <strong>${bailiff.imieNazwisko}</strong><br>
                                        <small style="color: #666;">${bailiff.adres}, ${bailiff.kodPocztowy} ${bailiff.miasto}</small>
                                    </div>
                                    <div style="display: flex; gap: 5px;">
                                        <button onclick="editBailiff(${bailiff.id}, event)" style="
                                            background: #28a745;
                                            color: white;
                                            border: none;
                                            padding: 8px 12px;
                                            border-radius: 6px;
                                            cursor: pointer;
                                            font-size: 12px;
                                        ">✏️ Edytuj</button>
                                        <button onclick="confirmDeleteBailiff(${bailiff.id}, '${bailiff.imie_nazwisko}', event)" style="
                                            background: #dc3545;
                                            color: white;
                                            border: none;
                                            padding: 8px 12px;
                                            border-radius: 6px;
                                            cursor: pointer;
                                            font-size: 12px;
                                        ">🗑️ Usuń</button>
                                    </div>
                                </div>
                            `).join('');
                            console.log('Odświeżono zawartość modalu z nowymi danymi');
                        }
                    }

                    // Pokaż powiadomienie o sukcesie
                    showEmployeeSearchStatus(`✅ ${result.message}`, 'success');
                } else {
                    alert(`Błąd: ${result.error}`);
                }
            } catch (error) {
                console.error('Błąd aktualizacji komornika:', error);
                console.error('Szczegóły błędu:', error.message, error.stack);
                alert('Wystąpił błąd podczas aktualizacji danych komornika');
            }
        }

        function updateFormularzeWithEditedBailiff(bailiffId, updatedBailiff) {
            console.log('Aktualizacja formularzy dla komornika:', bailiffId, updatedBailiff);

            // Najpierw znajdź stare dane komornika przed aktualizacją
            const oldBailiff = predefinedBailiffs.find(b => b.id === bailiffId);
            const oldName = oldBailiff ? oldBailiff.imieNazwisko : null;

            console.log('Stara nazwa komornika:', oldName);

            // Teraz zaktualizuj tablicę predefinedBailiffs
            const bailiffIndex = predefinedBailiffs.findIndex(b => b.id === bailiffId);
            if (bailiffIndex !== -1) {
                predefinedBailiffs[bailiffIndex] = {
                    id: updatedBailiff.id,
                    imieNazwisko: updatedBailiff.imie_nazwisko,
                    adres: updatedBailiff.adres,
                    miasto: updatedBailiff.miasto,
                    kodPocztowy: updatedBailiff.kod_pocztowy,
                    telefon: updatedBailiff.telefon,
                    email: updatedBailiff.email,
                    sadRejonowy: updatedBailiff.sad_rejonowy
                };
                console.log('Zaktualizowano tablicę predefinedBailiffs');
            }

            // Sprawdź wszystkie formularze czy któryś używa edytowanego komornika
            // Sprawdź główny formularz komornika
            const mainBailiffNameInput = document.querySelector('input[name="bailiffName"]');
            if (mainBailiffNameInput && mainBailiffNameInput.value.trim()) {
                console.log('Sprawdzam główny formularz, obecna nazwa:', mainBailiffNameInput.value.trim());
                // Sprawdź czy to jest ten sam komornik (porównaj przez starą nazwę)
                if (oldName && mainBailiffNameInput.value.trim() === oldName) {
                    console.log('Aktualizuję główny formularz');
                    // Zaktualizuj główny formularz
                    mainBailiffNameInput.value = updatedBailiff.imie_nazwisko;
                    const mainBailiffAddressInput = document.querySelector('input[name="bailiffAddress"]');
                    const mainBailiffCityInput = document.querySelector('input[name="bailiffCity"]');
                    if (mainBailiffAddressInput) mainBailiffAddressInput.value = updatedBailiff.adres;
                    if (mainBailiffCityInput) mainBailiffCityInput.value = `${updatedBailiff.kod_pocztowy} ${updatedBailiff.miasto}`;
                }
            }

            // Sprawdź dodatkowe formularze komorników
            for (let i = 0; i < 10; i++) { // sprawdź do 10 dodatkowych formularzy
                const additionalNameInput = document.querySelector(`input[name="additionalBailiffName${i}"]`);
                if (additionalNameInput && additionalNameInput.value.trim()) {
                    console.log(`Sprawdzam dodatkowy formularz ${i}, obecna nazwa:`, additionalNameInput.value.trim());
                    // Sprawdź czy to jest ten sam komornik (porównaj przez starą nazwę)
                    if (oldName && additionalNameInput.value.trim() === oldName) {
                        console.log(`Aktualizuję dodatkowy formularz ${i}`);
                        // Zaktualizuj dodatkowy formularz
                        additionalNameInput.value = updatedBailiff.imie_nazwisko;
                        const additionalAddressInput = document.querySelector(`input[name="additionalBailiffAddress${i}"]`);
                        const additionalCityInput = document.querySelector(`input[name="additionalBailiffCity${i}"]`);
                        if (additionalAddressInput) additionalAddressInput.value = updatedBailiff.adres;
                        if (additionalCityInput) additionalCityInput.value = `${updatedBailiff.kod_pocztowy} ${updatedBailiff.miasto}`;

                        // Zaktualizuj notice o automatycznym wypełnieniu
                        const autoFilledNotice = document.getElementById(`autoFilledNotice${i}`);
                        if (autoFilledNotice) {
                            autoFilledNotice.innerHTML = `✅ Dane zostały automatycznie uzupełnione z bazy: <strong>${updatedBailiff.imie_nazwisko}</strong>`;
                        }
                    }
                }
            }

            // Odśwież podsumowanie komorników
            updateBailiffSummary();
            console.log('Zakończono aktualizację formularzy');
        }

        function hideButtonsAndShowAutoFilledNotice(formIndex, bailiffName) {
            // Ukryj przyciski wyboru/dodawania
            const buttonsGroup = document.getElementById(`bailiffButtons${formIndex}`);
            if (buttonsGroup) {
                buttonsGroup.classList.add('auto-filled');

                // Dodaj informację o automatycznym uzupełnieniu
                const notice = document.createElement('div');
                notice.className = 'auto-filled-notice';
                notice.id = `autoFilledNotice${formIndex}`;
                notice.innerHTML = `
                    <span>🤖</span>
                    <span>Dane komornika "${bailiffName}" zostały uzupełnione automatycznie z bazy danych.</span>
                    <button type="button" onclick="showButtonsAndRemoveNotice(${formIndex})" style="
                        background: none; 
                        border: 1px solid #4caf50; 
                        color: #2e7d32; 
                        padding: 2px 8px; 
                        border-radius: 4px; 
                        font-size: 12px; 
                        margin-left: auto;
                        cursor: pointer;
                    ">Usuń komornika</button>
                `;

                // Wstaw przed grid z danymi komornika
                const bailiffGrid = buttonsGroup.nextElementSibling;
                buttonsGroup.parentNode.insertBefore(notice, bailiffGrid);
            }
        }

        function showButtonsAndRemoveNotice(formIndex) {
            // Pokaż przyciski
            const buttonsGroup = document.getElementById(`bailiffButtons${formIndex}`);
            if (buttonsGroup) {
                buttonsGroup.classList.remove('auto-filled');
            }

            // Usuń informację
            const notice = document.getElementById(`autoFilledNotice${formIndex}`);
            if (notice) {
                notice.remove();
            }

            // Wyczyść pola
            const nameInput = document.querySelector(`input[name="additionalBailiffName${formIndex}"]`);
            const addressInput = document.querySelector(`input[name="additionalBailiffAddress${formIndex}"]`);
            const cityInput = document.querySelector(`input[name="additionalBailiffCity${formIndex}"]`);
            const caseInput = document.querySelector(`input[name="additionalBailiffCase${formIndex}"]`);
            const dateInput = document.querySelector(`input[name="additionalBailiffDate${formIndex}"]`);

            if (nameInput) nameInput.value = '';
            if (addressInput) addressInput.value = '';
            if (cityInput) cityInput.value = '';
            if (caseInput) caseInput.value = '';
            if (dateInput) dateInput.value = '';

            updateBailiffSummary();
        }

        function hideButtonsAndShowManualFilledNotice(formIndex, bailiffName) {
            // Ukryj przyciski wyboru/dodawania
            const buttonsGroup = document.getElementById(`bailiffButtons${formIndex}`);
            if (buttonsGroup) {
                buttonsGroup.classList.add('auto-filled');

                // Dodaj informację o ręcznym uzupełnieniu
                const notice = document.createElement('div');
                notice.className = 'auto-filled-notice';
                notice.id = `autoFilledNotice${formIndex}`;
                notice.innerHTML = `
                    <span>✏️</span>
                    <span>Dane komornika "${bailiffName}" zostały uzupełnione ręcznie.</span>
                    <button type="button" onclick="showButtonsAndRemoveNotice(${formIndex})" style="
                        background: none; 
                        border: 1px solid #4caf50; 
                        color: #2e7d32; 
                        padding: 2px 8px; 
                        border-radius: 4px; 
                        font-size: 12px; 
                        margin-left: auto;
                        cursor: pointer;
                    ">Usuń komornika</button>
                `;

                // Wstaw przed grid z danymi komornika
                const bailiffGrid = buttonsGroup.nextElementSibling;
                if (bailiffGrid) {
                    buttonsGroup.parentNode.insertBefore(notice, bailiffGrid);
                }
            }
        }

        function openAddBailiffForm() {
            // Zamknij poprzedni modal
            closeBailiffSelector();

            // Stwórz modal do dodawania komornika
            const modal = document.createElement('div');
            modal.className = 'add-bailiff-modal';
            modal.style.cssText = `
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: rgba(0, 0, 0, 0.7);
                display: flex;
                justify-content: center;
                align-items: center;
                z-index: 10000;
                font-family: Arial, sans-serif;
            `;

            const modalContent = document.createElement('div');
            modalContent.style.cssText = `
                background: white;
                padding: 30px;
                border-radius: 15px;
                width: 500px;
                max-width: 90vw;
                max-height: 90vh;
                overflow-y: auto;
                box-shadow: 0 20px 40px rgba(0,0,0,0.3);
            `;

            modalContent.innerHTML = `
                <h3 style="margin-bottom: 25px; color: #2a5298; text-align: center;">
                    ➕ Dodaj nowego komornika
                </h3>
                <form id="addBailiffForm" style="display: flex; flex-direction: column; gap: 15px;">
                    <div>
                        <label style="display: block; margin-bottom: 5px; font-weight: bold; color: #333;">
                            Imię i nazwisko *
                        </label>
                        <input type="text" id="bailiff_name" required style="
                            width: 100%;
                            padding: 10px;
                            border: 2px solid #cbd5e0;
                            border-radius: 8px;
                            font-size: 14px;
                            box-sizing: border-box;
                        " placeholder="np. Anna Kowalska">
                    </div>
                    
                    <div>
                        <label style="display: block; margin-bottom: 5px; font-weight: bold; color: #333;">
                            Płeć *
                        </label>
                        <select id="bailiff_gender" required style="
                            width: 100%;
                            padding: 10px;
                            border: 2px solid #cbd5e0;
                            border-radius: 8px;
                            font-size: 14px;
                            box-sizing: border-box;
                        ">
                            <option value="">Wybierz płeć</option>
                            <option value="k">Kobieta</option>
                            <option value="m">Mężczyzna</option>
                        </select>
                    </div>
                    
                    <div>
                        <label style="display: block; margin-bottom: 5px; font-weight: bold; color: #333;">
                            Adres *
                        </label>
                        <input type="text" id="bailiff_address" required style="
                            width: 100%;
                            padding: 10px;
                            border: 2px solid #cbd5e0;
                            border-radius: 8px;
                            font-size: 14px;
                            box-sizing: border-box;
                        " placeholder="np. ul. Piotrkowska 123">
                    </div>
                    
                    <div style="display: flex; gap: 10px;">
                        <div style="flex: 1;">
                            <label style="display: block; margin-bottom: 5px; font-weight: bold; color: #333;">
                                Kod pocztowy *
                            </label>
                            <input type="text" id="bailiff_postal" required pattern="[0-9]{2}-[0-9]{3}" style="
                                width: 100%;
                                padding: 10px;
                                border: 2px solid #cbd5e0;
                                border-radius: 8px;
                                font-size: 14px;
                                box-sizing: border-box;
                            " placeholder="90-001">
                        </div>
                        
                        <div style="flex: 2;">
                            <label style="display: block; margin-bottom: 5px; font-weight: bold; color: #333;">
                                Miasto *
                            </label>
                            <input type="text" id="bailiff_city" required style="
                                width: 100%;
                                padding: 10px;
                                border: 2px solid #cbd5e0;
                                border-radius: 8px;
                                font-size: 14px;
                                box-sizing: border-box;
                            " placeholder="Łódź">
                        </div>
                    </div>
                    
                    <div>
                        <label style="display: block; margin-bottom: 5px; font-weight: bold; color: #333;">
                            Telefon
                        </label>
                        <input type="tel" id="bailiff_phone" style="
                            width: 100%;
                            padding: 10px;
                            border: 2px solid #cbd5e0;
                            border-radius: 8px;
                            font-size: 14px;
                            box-sizing: border-box;
                        " placeholder="42-123-45-67">
                    </div>
                    
                    <div>
                        <label style="display: block; margin-bottom: 5px; font-weight: bold; color: #333;">
                            Email
                        </label>
                        <input type="email" id="bailiff_email" style="
                            width: 100%;
                            padding: 10px;
                            border: 2px solid #cbd5e0;
                            border-radius: 8px;
                            font-size: 14px;
                            box-sizing: border-box;
                        " placeholder="email@komornik.pl">
                    </div>
                    
                    <div>
                        <label style="display: block; margin-bottom: 5px; font-weight: bold; color: #333;">
                            Sąd rejonowy
                        </label>
                        <input type="text" id="bailiff_court" style="
                            width: 100%;
                            padding: 10px;
                            border: 2px solid #cbd5e0;
                            border-radius: 8px;
                            font-size: 14px;
                            box-sizing: border-box;
                        " placeholder="Sąd Rejonowy w Łodzi">
                    </div>
                    
                    <div style="display: flex; gap: 10px; margin-top: 20px;">
                        <button type="submit" style="
                            flex: 1;
                            padding: 15px;
                            background: #28a745;
                            color: white;
                            border: none;
                            border-radius: 8px;
                            cursor: pointer;
                            font-weight: bold;
                            font-size: 16px;
                        ">💾 Zapisz komornika</button>
                        
                        <button type="button" onclick="closeAddBailiffForm()" style="
                            flex: 1;
                            padding: 15px;
                            background: #6c757d;
                            color: white;
                            border: none;
                            border-radius: 8px;
                            cursor: pointer;
                            font-size: 16px;
                        ">Anuluj</button>
                    </div>
                </form>
            `;

            modal.appendChild(modalContent);
            document.body.appendChild(modal);

            // Obsługa formularza
            document.getElementById('addBailiffForm').addEventListener('submit', saveBailiff);

            // Zamykanie na kliknięcie tła
            modal.addEventListener('click', (e) => {
                if (e.target === modal) {
                    closeAddBailiffForm();
                }
            });
        }

        function closeAddBailiffForm() {
            const modal = document.querySelector('.add-bailiff-modal');
            if (modal) {
                modal.remove();
            }
        }

        async function saveBailiff(event) {
            event.preventDefault();

            const formData = {
                imie_nazwisko: document.getElementById('bailiff_name').value.trim(),
                plec: document.getElementById('bailiff_gender').value,
                adres: document.getElementById('bailiff_address').value.trim(),
                kod_pocztowy: document.getElementById('bailiff_postal').value.trim(),
                miasto: document.getElementById('bailiff_city').value.trim(),
                telefon: document.getElementById('bailiff_phone').value.trim(),
                email: document.getElementById('bailiff_email').value.trim(),
                sad_rejonowy: document.getElementById('bailiff_court').value.trim()
            };

            // Walidacja wymaganych pól
            if (!formData.imie_nazwisko || !formData.plec || !formData.adres || !formData.kod_pocztowy || !formData.miasto) {
                showEmployeeSearchStatus('❌ Proszę wypełnić wszystkie wymagane pola (oznaczone *)', 'error');
                return;
            }

            // Walidacja kodu pocztowego
            const postalRegex = /^[0-9]{2}-[0-9]{3}$/;
            if (!postalRegex.test(formData.kod_pocztowy)) {
                showEmployeeSearchStatus('❌ Kod pocztowy musi być w formacie XX-XXX', 'error');
                return;
            }

            try {
                const response = await fetch('/api/add-bailiff', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(formData)
                });

                const result = await response.json();

                if (response.ok) {
                    showEmployeeSearchStatus(`✅ Komornik ${formData.imie_nazwisko} został dodany pomyślnie!`, 'success');
                    closeAddBailiffForm();

                    // Odśwież listę komorników
                    await loadBailiffsFromDatabase();

                    // Sprawdź czy modal wyboru komornika jest otwarty i odśwież go
                    const selectorModal = document.querySelector('.bailiff-selector-modal');
                    if (selectorModal) {
                        console.log('Modal jest otwarty po dodaniu nowego komornika, odświeżam jego zawartość');
                        const bailiffList = selectorModal.querySelector('.bailiff-list');
                        if (bailiffList) {
                            const currentBailiffIndex = window.currentBailiffSelectorIndex || 0;

                            // Wygeneruj nową listę HTML z nowym komornikiem
                            bailiffList.innerHTML = predefinedBailiffs.map((bailiff, index) => `
                                <div class="bailiff-option" style="
                                    padding: 15px;
                                    border: 2px solid #cbd5e0;
                                    border-radius: 10px;
                                    margin-bottom: 10px;
                                    transition: all 0.3s ease;
                                    display: flex;
                                    justify-content: space-between;
                                    align-items: center;
                                " onmouseover="this.style.borderColor='#2a5298'; this.style.background='#e6f2ff';" 
                                   onmouseout="this.style.borderColor='#cbd5e0'; this.style.background='white';">
                                    <div onclick="selectBailiff(${index}, ${currentBailiffIndex})" style="flex: 1; cursor: pointer;">
                                        <strong>${bailiff.imieNazwisko}</strong><br>
                                        <small style="color: #666;">${bailiff.adres}, ${bailiff.kodPocztowy} ${bailiff.miasto}</small>
                                    </div>
                                    <div style="display: flex; gap: 5px;">
                                        <button onclick="editBailiff(${bailiff.id}, event)" style="
                                            background: #007bff;
                                            color: white;
                                            border: none;
                                            padding: 8px 12px;
                                            border-radius: 6px;
                                            cursor: pointer;
                                            font-size: 12px;
                                        ">✏️ Edytuj</button>
                                        <button onclick="confirmDeleteBailiff(${bailiff.id}, '${bailiff.imieNazwisko}', event)" style="
                                            background: #dc3545;
                                            color: white;
                                            border: none;
                                            padding: 8px 12px;
                                            border-radius: 6px;
                                            cursor: pointer;
                                            font-size: 12px;
                                        ">🗑️ Usuń</button>
                                    </div>
                                </div>
                            `).join('');
                            console.log('Lista w modalu została odświeżona z nowym komornikiem');
                        }
                    }
                } else {
                    showEmployeeSearchStatus(`❌ ${result.error}`, 'error');
                }
            } catch (error) {
                console.error('Błąd dodawania komornika:', error);
                showEmployeeSearchStatus('❌ Wystąpił błąd podczas dodawania komornika', 'error');
            }
        }

        function updateBailiffSummary() {
            const summaryContainer = document.getElementById('bailiffSummary');
            const additionalBailiffs = document.querySelectorAll('.bailiff-entry');

            if (additionalBailiffs.length === 0) {
                summaryContainer.innerHTML = '';
                return;
            }

            let summaryHTML = '<h4>Podsumowanie komorników:</h4>';

            summaryHTML += `
                <div class="bailiff-summary">
                    <strong>Komornik A (główny):</strong> ${document.getElementById('zbiegBailiffA_Name').value}<br>
                    <strong>Sprawa:</strong> ${document.getElementById('zbiegBailiffA_Case').value}<br>
                    <strong>Data wpływu:</strong> ${document.getElementById('zbiegDate').value}
                </div>
            `;

            additionalBailiffs.forEach((bailiff, index) => {
                const inputs = bailiff.querySelectorAll('input');
                const name = inputs[0].value;
                const caseNum = inputs[1].value;
                const address = inputs[2].value;
                const city = inputs[3].value;
                const date = inputs[4].value;

                // Pobierz rzeczywisty indeks z nazwy pola input
                const nameInput = inputs[0];
                const bailiffIndex = nameInput.name.match(/additionalBailiffName(\d+)/)[1];

                summaryHTML += `
                    <div class="bailiff-summary">
                        <strong>Komornik ${String.fromCharCode(66 + index)}:</strong> ${name || '[nie podano]'}<br>
                        <strong>Sprawa:</strong> ${caseNum || '[nie podano]'}<br>
                        <strong>Data wpływu:</strong> ${date || '[nie podano]'}
                    </div>
                `;

                // Sprawdź czy pola są wypełnione ręcznie (nie przez auto-fill)
                const buttonsGroup = document.getElementById(`bailiffButtons${bailiffIndex}`);
                const notice = document.getElementById(`autoFilledNotice${bailiffIndex}`);

                if (name && address && city && caseNum && date && !notice) {
                    // Pola są wypełnione ręcznie - ukryj przyciski i pokaż informację
                    if (buttonsGroup && !buttonsGroup.classList.contains('auto-filled')) {
                        hideButtonsAndShowManualFilledNotice(bailiffIndex, name);
                    }
                } else if (!name && !address && !city && !caseNum && !date && !notice) {
                    // Pola są puste i nie ma auto-fill - pokaż przyciski
                    if (buttonsGroup && buttonsGroup.classList.contains('auto-filled')) {
                        showButtonsAndRemoveNotice(bailiffIndex);
                    }
                }
            });

            summaryContainer.innerHTML = summaryHTML;
        }

        async function generateLetters() {
            if (!selectedOption) {
                showToast('Wybierz opcję weryfikacji!', 'warning');
                return;
            }

            // Pokaż postęp i zablokuj przycisk
            const generateBtn = document.getElementById('generateBtn');
            generateBtn.textContent = 'Generuję...';
            generateBtn.disabled = true;

            const payload = {
                option: selectedOption,
                company: currentSender ? currentSender.nazwa : '',
                sender: currentSender ? {
                    nazwa: currentSender.nazwa,
                    adres: currentSender.adres,
                    miasto: currentSender.miasto,
                    telefon: currentSender.telefon,
                    email: currentSender.email
                } : null,
                dane: {
                    komornik: {
                        imieNazwisko: document.getElementById('editBailiffName').value,
                        adres: document.getElementById('editBailiffAddress').value,
                        miasto: document.getElementById('editBailiffCity').value,
                        kontakt: document.getElementById('editBailiffContact').value
                    },
                    dluznik: {
                        imieNazwisko: document.getElementById('editDebtorName').value,
                        pesel: document.getElementById('editDebtorPesel').value
                    },
                    sprawa: {
                        sygnaturaSprawy: document.getElementById('editCaseNumber').value,
                        numerRachunku: document.getElementById('editBankAccount').value
                    },
                    dataZakonczania: (selectedOption === 1 && document.getElementById('endDate')) ? document.getElementById('endDate').value : null,
                    umowy: {
                        zlecenie: (selectedOption === 3 && document.getElementById('contractType1')) ? document.getElementById('contractType1').checked : false,
                        najem: (selectedOption === 3 && document.getElementById('contractType2')) ? document.getElementById('contractType2').checked : false
                    },
                    komornicy: []
                }
            };
            // NOWA LOGIKA: jeśli tryb universal (checkbox niezaznaczony), generuj bez kroku 3
            if (!isKomorniczeSelected) {
                // Zbierz wartości pól z formularza
                const updatedFields = (window.currentFields || []).map(field => ({
                    ...field,
                    value: document.getElementById(`ufield_${field.id}`)?.value || field.value
                }));

                try {
                    const response = await fetch('/generate-universal-letter', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            category: window.currentClassification.category,
                            subtype: window.currentClassification.subtype,
                            fields: updatedFields,
                            company: currentSender ? currentSender.nazwa : '',
                            sender: currentSender || null,
                            scenario: document.getElementById('universal-scenario')?.value || null
                        })
                    });

                    const result = await response.json();
                    if (response.ok) {
                        allGeneratedLetters = [{
                            title: result.title,
                            content: result.list,
                            bailiff: { imieNazwisko: window.currentClassification.subtype }
                        }];
                        currentLetterIndex = 0;
                        displayMultipleLetters(allGeneratedLetters);
                        goToStep(4);
                    } else {
                        alert('Błąd generowania listu: ' + result.error);
                    }
                } catch (error) {
                    alert('Nie udało się połączyć z serwerem.');
                } finally {
                    generateBtn.textContent = 'Generuj Listy';
                    generateBtn.disabled = false;
                }
                return; // ważne - zatrzymaj dalsze wykonanie
            }

            if (selectedOption == 4) {
                // Dodaj główny komornik ze zbiegu
                payload.dane.komornicy.push({
                    imieNazwisko: document.getElementById('zbiegBailiffA_Name').value,
                    adres: document.getElementById('zbiegBailiffA_Address').value,
                    miasto: document.getElementById('zbiegBailiffA_City').value,
                    sygnaturaSprawy: document.getElementById('zbiegBailiffA_Case').value,
                    dataWplywu: document.getElementById('zbiegDate').value
                });

                // Dodaj dodatkowych komorników
                const additionalBailiffs = document.querySelectorAll('.bailiff-entry');
                additionalBailiffs.forEach((bailiff) => {
                    const inputs = bailiff.querySelectorAll('input');
                    payload.dane.komornicy.push({
                        imieNazwisko: inputs[0].value,
                        adres: inputs[2].value,
                        miasto: inputs[3].value,
                        sygnaturaSprawy: inputs[1].value,
                        dataWplywu: inputs[4].value
                    });
                });

                // Generuj osobny list dla każdego komornika w przypadku zbiegu
                try {
                    const response = await fetch('/generate-zbieg-letters', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(payload)
                    });

                    const result = await response.json();

                    if (response.ok) {
                        allGeneratedLetters = result.listy;
                        currentLetterIndex = 0;
                        displayMultipleLetters(allGeneratedLetters);
                        goToStep(4);
                    } else {
                        alert('Błąd generowania listów: ' + result.error);
                        // Przywróć tekst przycisku w przypadku błędu
                        generateBtn.textContent = 'Generuj Listy';
                        generateBtn.disabled = false;
                    }
                } catch (error) {
                    console.error('Błąd połączenia z serwerem:', error);
                    alert('Nie udało się połączyć z serwerem. Sprawdź, czy serwer działa.');
                    // Przywróć tekst przycisku w przypadku błędu
                    generateBtn.textContent = 'Generuj Listy';
                    generateBtn.disabled = false;
                }
            } else {
                // Standardowe generowanie jednego listu
                try {
                    const response = await fetch('/generate-letter', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(payload)
                    });

                    const result = await response.json();

                    if (response.ok) {
                        allGeneratedLetters = [{ title: 'Wygenerowany List', content: result.list, bailiff: payload.dane.komornik }];
                        currentLetterIndex = 0;
                        displayMultipleLetters(allGeneratedLetters);
                        goToStep(4);
                    } else {
                        alert('Błąd generowania listu: ' + result.error);
                        // Przywróć tekst przycisku w przypadku błędu
                        generateBtn.textContent = 'Generuj Listy';
                        generateBtn.disabled = false;
                    }
                } catch (error) {
                    console.error('Błąd połączenia z serwerem:', error);
                    alert('Nie udało się połączyć z serwerem. Sprawdź, czy serwer działa.');
                    // Przywróć tekst przycisku w przypadku błędu
                    generateBtn.textContent = 'Generuj Listy';
                    generateBtn.disabled = false;
                }
            }

            // Przywróć oryginalny tekst i odblokuj przycisk
            generateBtn.textContent = 'Generuj Listy';
            generateBtn.disabled = false;
        }

        function displayLetters(letters) {
            const container = document.getElementById('generatedLetters');
            container.innerHTML = '';

            if (letters.length > 1) {
                container.innerHTML += `<div style="background: #e7f3ff; padding: 15px; border-radius: 10px; margin-bottom: 20px;"><strong>📄 Wygenerowano ${letters.length} listów</strong></div>`;
            }

            letters.forEach((letter, index) => {
                const letterDiv = document.createElement('div');
                letterDiv.innerHTML = `
                    <div style="margin-bottom: 20px;">
                        <h3>${letter.title}</h3>
                        <button class="btn-secondary btn btn-small" onclick="downloadLetter(${index})">📥 Pobierz PDF</button>
                        <button class="btn-secondary btn btn-small" onclick="copyLetter(${index})">📋 Kopiuj</button>
                        <button class="btn-secondary btn btn-small" onclick="editDate(${index})">📅 Zmień datę</button>
                    </div>
                    <div class="letter-preview">
                        ${letter.content}
                    </div>
                `;
                container.appendChild(letterDiv);
            });

            window.generatedLetters = letters;
        }

        function displayMultipleLetters(letters) {
            const container = document.getElementById('generatedLetters');
            container.innerHTML = '';

            if (letters.length > 1) {
                // Informacja o wielu listach
                const infoDiv = document.createElement('div');
                infoDiv.className = 'multiple-letters-info';
                infoDiv.innerHTML = `
                    <h3>📄 Zbieg Komorniczy - Wygenerowano ${letters.length} listów</h3>
                    <p>Każdy komornik otrzyma osobny list z informacją o pozostałych komornikach w sprawie.</p>
                `;
                container.appendChild(infoDiv);

                // Sekcja pobierania
                const downloadDiv = document.createElement('div');
                downloadDiv.className = 'download-section';
                downloadDiv.innerHTML = `
                    <h4>📥 Pobieranie listów:</h4>
                    <div style="margin-bottom: 15px;">
                        <strong>Bieżący list:</strong><br>
                        <button class="btn btn-small" onclick="downloadCurrentLetter('doc')">📄 DOC</button>
                        <button class="btn btn-small" onclick="downloadCurrentLetter('pdf')">📃 PDF</button>
                    </div>
                    <div>
                        <strong>Wszystkie listy (${letters.length}):</strong><br>
                        <button class="btn btn-small" onclick="downloadAllLetters('doc', this)">📄 Wszystkie DOC</button>
                        <button class="btn btn-small" onclick="downloadAllLetters('pdf', this)">📃 Wszystkie PDF</button>
                    </div>
                `;
                container.appendChild(downloadDiv);

                // Nawigacja
                const navDiv = document.createElement('div');
                navDiv.className = 'letter-navigation';
                navDiv.innerHTML = `
                    <button class="nav-button" id="prevBtn" onclick="previousLetter()">← Poprzedni</button>
                    <div class="letter-counter">
                        <span id="currentLetterNum">1</span> z <span id="totalLetters">${letters.length}</span>
                    </div>
                    <button class="nav-button" id="nextBtn" onclick="nextLetter()">Następny →</button>
                `;
                container.appendChild(navDiv);
            }

            // Dodaj wszystkie listy (ukryte)
            letters.forEach((letter, index) => {
                const letterDiv = document.createElement('div');
                letterDiv.className = 'letter-preview';
                letterDiv.id = `letter-${index}`;
                if (index === 0) letterDiv.classList.add('active');

                letterDiv.innerHTML = `
                    <div style="margin-bottom: 20px; text-align: center; background: #f8f9fa; padding: 15px; border-radius: 8px;">
                        <h3>${letter.title}</h3>
                        <p style="margin: 5px 0; color: #6c757d;">Adresat: ${letter.bailiff ? letter.bailiff.imieNazwisko : 'Nieznany'}</p>
                        <div style="margin-top: 10px;">
                            <button class="btn-secondary btn btn-small" onclick="downloadLetter(${index}, 'doc')">📄 DOC</button>
                            <button class="btn-secondary btn btn-small" onclick="downloadLetter(${index}, 'pdf')">📃 PDF</button>
                            <button class="btn-secondary btn btn-small" onclick="copyLetter(${index})">📋 Kopiuj treść</button>
                            <button class="btn-secondary btn btn-small" onclick="editLetterDate(${index})">📅 Zmień datę</button>
                        </div>
                    </div>
                    <div style="min-height: 600px;">
                        ${letter.content}
                    </div>
                `;
                container.appendChild(letterDiv);
            });

            updateNavigationButtons();
            allGeneratedLetters = letters;
        }

        function previousLetter() {
            if (currentLetterIndex > 0) {
                document.getElementById(`letter-${currentLetterIndex}`).classList.remove('active');
                currentLetterIndex--;
                document.getElementById(`letter-${currentLetterIndex}`).classList.add('active');
                updateNavigationButtons();
            }
        }

        function nextLetter() {
            if (currentLetterIndex < allGeneratedLetters.length - 1) {
                document.getElementById(`letter-${currentLetterIndex}`).classList.remove('active');
                currentLetterIndex++;
                document.getElementById(`letter-${currentLetterIndex}`).classList.add('active');
                updateNavigationButtons();
            }
        }

        function updateNavigationButtons() {
            const currentNumEl = document.getElementById('currentLetterNum');
            const prevBtn = document.getElementById('prevBtn');
            const nextBtn = document.getElementById('nextBtn');

            if (currentNumEl) currentNumEl.textContent = currentLetterIndex + 1;
            if (prevBtn) prevBtn.disabled = currentLetterIndex === 0;
            if (nextBtn) nextBtn.disabled = currentLetterIndex === allGeneratedLetters.length - 1;
        }

        // Obsługa klawiszy strzałek
        document.addEventListener('keydown', function (event) {
            if (currentStep === 4 && allGeneratedLetters.length > 1) {
                if (event.key === 'ArrowLeft') {
                    event.preventDefault();
                    previousLetter();
                } else if (event.key === 'ArrowRight') {
                    event.preventDefault();
                    nextLetter();
                }
            }
        });

        function editDate(index) {
            const newDate = prompt('Podaj nową datę (DD.MM.RRRR):', new Date().toLocaleDateString('pl-PL'));
            if (newDate) {
                const letter = window.generatedLetters[index];
                letter.content = letter.content.replace(/Łódź, \d{1,2}\.\d{1,2}\.\d{4}/, `Łódź, ${newDate}`);
                displayLetters(window.generatedLetters);
            }
        }

        function editLetterDate(index) {
            const newDate = prompt('Podaj nową datę (DD.MM.RRRR):', new Date().toLocaleDateString('pl-PL'));
            if (newDate && newDate.trim() !== '') {
                const letter = allGeneratedLetters[index];

                // Zaktualizuj datę w różnych formatach które mogą występować w dokumencie
                const datePatterns = [
                    /Łódź,\s*dnia\s*\d{1,2}[^\d]*\d{4}\s*r\./g,
                    /Łódź,\s*\d{1,2}\.\d{1,2}\.\d{4}/g,
                    /Łódź,\s*dnia\s*\d{1,2}\.\d{1,2}\.\d{4}\s*r\./g,
                    /<div class="date">.*?<\/div>/g
                ];

                let updatedContent = letter.content;

                // Zaktualizuj wszystkie możliwe formaty daty
                datePatterns.forEach(pattern => {
                    if (pattern.test(updatedContent)) {
                        if (pattern.source.includes('class="date"')) {
                            updatedContent = updatedContent.replace(pattern, `<div class="date">Łódź, dnia ${newDate} r.</div>`);
                        } else {
                            updatedContent = updatedContent.replace(pattern, `Łódź, dnia ${newDate} r.`);
                        }
                    }
                });

                // Jeśli nie znaleziono wzorców, spróbuj uniwersalnego
                if (updatedContent === letter.content) {
                    updatedContent = updatedContent.replace(/Łódź[^<\n]*/g, `Łódź, dnia ${newDate} r.`);
                }

                letter.content = updatedContent;
                // Odśwież wyświetlany list
                document.getElementById(`letter-${index}`).innerHTML = `
                    <div style="margin-bottom: 20px; text-align: center; background: #f8f9fa; padding: 15px; border-radius: 8px;">
                        <h3>${letter.title}</h3>
                        <p style="margin: 5px 0; color: #6c757d;">Adresat: ${letter.bailiff ? letter.bailiff.imieNazwisko : 'Nieznany'}</p>
                        <div style="margin-top: 10px;">
                            <button class="btn-secondary btn btn-small" onclick="downloadLetter(${index}, 'doc')">📄 DOC</button>
                            <button class="btn-secondary btn btn-small" onclick="downloadLetter(${index}, 'pdf')">📃 PDF</button>
                            <button class="btn-secondary btn btn-small" onclick="copyLetter(${index})">📋 Kopiuj treść</button>
                            <button class="btn-secondary btn btn-small" onclick="editLetterDate(${index})">📅 Zmień datę</button>
                        </div>
                    </div>
                    <div style="min-height: 600px;">
                        ${letter.content}
                    </div>
                `;
            }
        }

        function downloadLetter(index, format = 'doc') {
            const letter = allGeneratedLetters ? allGeneratedLetters[index] : window.generatedLetters[index];
            const bailiffName = letter.bailiff ? letter.bailiff.imieNazwisko.replace(/[^a-zA-Z0-9]/g, '_') : 'List';

            if (format === 'pdf') {
                downloadLetterAsPdf(index);
                return;
            } else if (format === 'doc') {
                downloadLetterAsDoc(index);
                return;
            }
        }

        async function downloadLetterAsPdf(index) {
            const letter = allGeneratedLetters ? allGeneratedLetters[index] : window.generatedLetters[index];

            // Debug informacje
            console.log('downloadLetterAsPdf - index:', index);
            console.log('downloadLetterAsPdf - letter:', letter);
            console.log('downloadLetterAsPdf - allGeneratedLetters:', allGeneratedLetters);
            console.log('downloadLetterAsPdf - window.generatedLetters:', window.generatedLetters);

            if (!letter) {
                alert('Nie znaleziono listu o podanym indeksie');
                return;
            }

            const bailiffName = letter.bailiff ? letter.bailiff.imieNazwisko.replace(/[^a-zA-Z0-9]/g, '_') : 'List';
            const fileName = `${bailiffName}_${letter.title.replace(/[^a-zA-Z0-9]/g, '_')}.pdf`;

            try {
                const response = await fetch('/download-pdf', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        html_content: letter.content,
                        filename: fileName
                    })
                });

                if (response.ok) {
                    const blob = await response.blob();
                    const url = window.URL.createObjectURL(blob);

                    // Pobierz plik PDF
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = fileName;
                    document.body.appendChild(a);
                    a.click();
                    window.URL.revokeObjectURL(url);
                    document.body.removeChild(a);
                } else {
                    const error = await response.json();
                    alert(`Błąd pobierania PDF: ${error.error}`);
                }
            } catch (error) {
                console.error('Błąd pobierania PDF:', error);
                alert('Nie udało się pobrać pliku PDF. Sprawdź połączenie z serwerem.');
            }
        }

        async function downloadLetterAsDoc(index) {
            const letter = allGeneratedLetters ? allGeneratedLetters[index] : window.generatedLetters[index];
            const bailiffName = letter.bailiff ? letter.bailiff.imieNazwisko.replace(/[^a-zA-Z0-9]/g, '_') : 'List';
            const fileName = `${bailiffName}_${letter.title.replace(/[^a-zA-Z0-9]/g, '_')}.docx`;

            try {
                const response = await fetch('/download-doc', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        html_content: letter.content,
                        filename: fileName
                    })
                });

                if (response.ok) {
                    const blob = await response.blob();
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = fileName;
                    document.body.appendChild(a);
                    a.click();
                    window.URL.revokeObjectURL(url);
                    document.body.removeChild(a);
                } else {
                    const error = await response.json();
                    alert(`Błąd pobierania DOC: ${error.error}`);
                }
            } catch (error) {
                console.error('Błąd pobierania DOC:', error);
                alert('Nie udało się pobrać pliku DOC. Sprawdź połączenie z serwerem.');
            }
        }

        function copyLetter(index) {
            const letter = allGeneratedLetters ? allGeneratedLetters[index] : window.generatedLetters[index];
            const tempDiv = document.createElement('div');
            tempDiv.innerHTML = letter.content;
            const textContent = tempDiv.textContent || tempDiv.innerText;

            navigator.clipboard.writeText(textContent).then(() => {
                alert('Treść listu została skopiowana do schowka!');
            });
        }

        function downloadAllLetters(format = 'doc', buttonElement = null) {
            const letters = allGeneratedLetters || window.generatedLetters;
            if (letters) {
                // Znajdź przycisk jeśli nie został przekazany
                if (!buttonElement) {
                    buttonElement = event ? event.target : null;
                }

                letters.forEach((letter, index) => {
                    setTimeout(() => downloadLetter(index, format), index * 2000); // Zwiększam opóźnienie
                });

                // Pokaż komunikat o pobieraniu
                if (buttonElement) {
                    const originalText = buttonElement.textContent;
                    const fileType = format === 'pdf' ? 'PDF' : (format === 'doc' ? 'DOC' : 'HTML');
                    buttonElement.textContent = `Pobieranie ${letters.length} plików ${fileType}...`;
                    buttonElement.disabled = true;

                    setTimeout(() => {
                        buttonElement.textContent = originalText;
                        buttonElement.disabled = false;
                        alert(`Pobrano ${letters.length} listów w formacie ${fileType}!`);
                    }, letters.length * 2000); // Zwiększam czas oczekiwania
                }
            }
        }

        function downloadCurrentLetter(format = 'html') {
            if (allGeneratedLetters && allGeneratedLetters[currentLetterIndex]) {
                downloadLetter(currentLetterIndex, format);
            }
        }

        function resetSystem() {
            currentStep = 1;
            selectedOption = null;
            fileData = null;
            additionalBailiffsCount = 0;
            bailiffsList = [];
            currentLetterIndex = 0;
            allGeneratedLetters = [];

            isKomorniczeSelected = false;
            const cbKom = document.getElementById('isKomorniczeCheck');
            if (cbKom) cbKom.checked = false;
            document.getElementById('step-indicator-3').style.display = 'none';
            const btn2n = document.getElementById('step2NextBtn');
            if (btn2n) btn2n.textContent = 'Generuj List ▶';

            currentSender = null;
            document.getElementById('senderSelect').value = '';
            document.getElementById('fileName').textContent = '';
            document.getElementById('fileInput').value = '';
            document.getElementById('additionalBailiffs').innerHTML = '';
            document.getElementById('bailiffSummary').innerHTML = '';
            document.querySelectorAll('input').forEach(input => {
                if (input.type !== 'radio' && input.type !== 'checkbox') {
                    input.value = '';
                } else {
                    input.checked = false;
                }
            });

            document.querySelectorAll('.radio-option').forEach(opt => opt.classList.remove('selected'));

            goToStep(1);
        }

        document.addEventListener('DOMContentLoaded', function () {
            const today = new Date().toISOString().split('T')[0];
            document.querySelectorAll('input[type="date"]').forEach(input => {
                if (!input.value) {
                    input.value = today;
                }
            });

            // Inicjalizuj bazę danych przy ładowaniu strony
            initializeDatabase();
            loadBailiffsFromDatabase();
            loadSenders();
            loadAccountInfo();
        });

        // Funkcje obsługi bazy danych
        let employeeData = null;
        let bailiffConflictInfo = null;

        async function initializeDatabase() {
            try {
                const response = await fetch('/api/initialize-database', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });

                const result = await response.json();
                if (response.ok) {
                    console.log('📊 Baza danych zainicjalizowana:', result.message);
                } else {
                    console.log('ℹ️ Baza danych:', result.error);
                }
            } catch (error) {
                console.log('⚠️ Problem z inicjalizacją bazy danych:', error);
            }
        }

        async function searchEmployeeInDatabase(pesel) {
            try {
                showEmployeeSearchStatus('Wyszukuję dane pracownika...');

                const response = await fetch(`/api/employee/${pesel}`);
                const result = await response.json();

                if (response.ok && result.found) {
                    employeeData = result.employee;
                    bailiffConflictInfo = result.bailiff_conflict;

                    // Uzupełnij brakujące dane pracownika
                    if (employeeData) {
                        updateEmployeeFields(employeeData);
                        showEmployeeSearchStatus(`✅ Znaleziono pracownika: ${employeeData.imie} ${employeeData.nazwisko} (${employeeData.spolka})`, 'success');

                        // Sprawdź zbieg komorniczy
                        if (bailiffConflictInfo.is_conflict) {
                            showBailiffConflictWarning(bailiffConflictInfo);
                        }

                        // Automatyczne wykrywanie scenariusza
                        await autoDetectScenario(pesel);
                    }
                } else {
                    showEmployeeSearchStatus('⚠️ Pracownik nie został znaleziony w bazie danych', 'warning');
                }
            } catch (error) {
                showEmployeeSearchStatus('❌ Błąd wyszukiwania w bazie danych', 'error');
                console.error('Błąd wyszukiwania pracownika:', error);
            }
        }

        function updateEmployeeFields(employee) {
            // Uzupełnij nazwisko pracownika jeśli brakuje
            const currentName = document.getElementById('editDebtorName').value;
            if (!currentName || currentName.trim() === '') {
                document.getElementById('editDebtorName').value = `${employee.imie} ${employee.nazwisko}`;
                document.getElementById('debtorName').textContent = `${employee.imie} ${employee.nazwisko}`;
            }

            // Uzupełnij numer rachunku jeśli brakuje
            const currentAccount = document.getElementById('editBankAccount').value;
            if (!currentAccount || currentAccount.trim() === '') {
                document.getElementById('editBankAccount').value = employee.numer_rachunku || '';
                document.getElementById('bankAccount').textContent = employee.numer_rachunku || '';
            }
        }

        async function autoDetectScenario(pesel) {
            try {
                const response = await fetch('/api/auto-detect-scenario', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ pesel: pesel })
                });

                const result = await response.json();

                if (response.ok) {
                    const scenario = result.scenario;
                    showAutoDetectionResult(scenario, result.reason);

                    // Opcjonalnie - automatyczne wybieranie scenariusza
                    // selectOption(scenario);
                }
            } catch (error) {
                console.error('Błąd automatycznego wykrywania scenariusza:', error);
            }
        }

        function showEmployeeSearchStatus(message, type = 'info') {
            // Usuń poprzednie powiadomienia
            const existingNotifications = document.querySelectorAll('.employee-search-notification');
            existingNotifications.forEach(n => n.remove());

            // Utwórz nowe powiadomienie
            const notification = document.createElement('div');
            notification.className = 'employee-search-notification';
            notification.style.cssText = `
                position: fixed;
                top: 80px;
                right: 20px;
                padding: 15px 20px;
                border-radius: 8px;
                color: white;
                font-weight: 500;
                z-index: 1000;
                max-width: 400px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.15);
                animation: slideIn 0.3s ease-out;
            `;

            // Kolory w zależności od typu
            const colors = {
                'info': '#2a5298',
                'success': '#28a745',
                'warning': '#ffc107',
                'error': '#dc3545'
            };

            notification.style.background = colors[type] || colors.info;
            notification.textContent = message;

            document.body.appendChild(notification);

            // Automatyczne usunięcie po 5 sekundach
            setTimeout(() => {
                if (notification.parentNode) {
                    notification.remove();
                }
            }, 5000);
        }

        function showBailiffConflictWarning(conflictInfo) {
            const message = `🚨 UWAGA: Wykryto ZBIEG KOMORNICZY!\n\nPracownik ma już ${conflictInfo.active_proceedings_count} aktywnych postępowań komorniczych.\n\nCzy chcesz automatycznie przejść do opcji "ZBIEG KOMORNICZY"?`;

            if (confirm(message)) {
                selectOption(4); // Automatyczne wybieranie opcji 4 - Zbieg komorniczy
                populateZbiegWithExistingData(conflictInfo.proceedings);
            }
        }

        function showAutoDetectionResult(scenario, reason) {
            const scenarioNames = {
                1: "Osoba NIE PRACUJE",
                2: "Błędne pismo (wynagrodzenie zamiast zajęcia)",
                3: "Osoba PRACUJE - zajęcie wierzytelności",
                4: "ZBIEG KOMORNICZY"
            };

            const message = `🤖 Automatyczne wykrywanie:\n\nZalecany scenariusz: ${scenarioNames[scenario]}\n\nPowód: ${reason}\n\nCzy chcesz automatycznie wybrać ten scenariusz?`;

            if (confirm(message)) {
                selectOption(scenario);
            }
        }

        function populateZbiegWithExistingData(proceedings) {
            // Uzupełnij dane z istniejących postępowań do formularza zbiegu
            if (proceedings && proceedings.length > 0) {
                const activeProceedings = proceedings.filter(p => p.status === 'aktywne');

                // Dodaj wszystkie istniejące postępowania jako dodatkowych komorników
                activeProceedings.forEach((proceeding, index) => {
                    addBailiff();
                    const entryNumber = additionalBailiffsCount;

                    // Uzupełnij dane (poprawne mapowanie pól)
                    document.querySelector(`input[name="additionalBailiffName${entryNumber}"]`).value = proceeding.bailiff_details.imie_nazwisko;
                    document.querySelector(`input[name="additionalBailiffCase${entryNumber}"]`).value = proceeding.sygnatura_sprawy;
                    document.querySelector(`input[name="additionalBailiffAddress${entryNumber}"]`).value = proceeding.bailiff_details.adres;
                    document.querySelector(`input[name="additionalBailiffCity${entryNumber}"]`).value = proceeding.bailiff_details.miasto;
                    document.querySelector(`input[name="additionalBailiffDate${entryNumber}"]`).value = proceeding.data_wplywu;
                });

                updateBailiffSummary();
                showEmployeeSearchStatus(`✅ Załadowano ${activeProceedings.length} istniejących postępowań komorniczych`, 'success');
            }
        }

        // CSS dla animacji
        const animationCSS = `
            @keyframes slideIn {
                from { transform: translateX(100%); opacity: 0; }
                to { transform: translateX(0); opacity: 1; }
            }
        `;

        // Dodaj CSS do strony
        // ── Loading Overlay ──────────────────────────────────────────

        const _loadingMessages = [
            'Wczytuję plik...',
            'Rozpoznaję tekst (OCR)...',
            'Klasyfikuję pismo...',
            'Wyciągam dane...'
        ];
        let _loadingMsgIndex = 0;
        let _loadingMsgTimer = null;

        function showLoadingOverlay() {
            _loadingMsgIndex = 0;
            const overlay = document.getElementById('loadingOverlay');
            const textEl  = document.getElementById('loadingText');
            textEl.textContent = _loadingMessages[0];
            overlay.classList.add('active');

            _loadingMsgTimer = setInterval(() => {
                _loadingMsgIndex = (_loadingMsgIndex + 1) % _loadingMessages.length;
                textEl.style.animation = 'none';
                void textEl.offsetWidth; // reflow
                textEl.style.animation = '';
                textEl.textContent = _loadingMessages[_loadingMsgIndex];
            }, 3000);
        }

        function hideLoadingOverlay() {
            clearInterval(_loadingMsgTimer);
            document.getElementById('loadingOverlay').classList.remove('active');
        }

        // ── Toast Notifications ───────────────────────────────────────

        function showToast(message, type) {
            type = type || 'info';
            const icons = { error: '❌', success: '✅', warning: '⚠️', info: 'ℹ️' };
            const container = document.getElementById('toastContainer');

            const toast = document.createElement('div');
            toast.className = 'toast ' + type;
            toast.innerHTML =
                '<span class="toast-icon">' + (icons[type] || 'ℹ️') + '</span>' +
                '<span class="toast-msg">' + escapeHtml(message) + '</span>';

            container.appendChild(toast);

            setTimeout(() => {
                toast.classList.add('hiding');
                toast.addEventListener('animationend', () => toast.remove(), { once: true });
            }, 4500);
        }

        // ── Walidacja przejścia do kroku 3 ───────────────────────────

        function validateAndGoToStep3() {
            if (!currentSender) {
                showToast('Wybierz nadawcę pisma przed przejściem dalej.', 'warning');
                document.getElementById('senderSelect').focus();
                return;
            }
            if (isKomorniczeSelected) {
                goToStep(3);
            } else {
                generateLetters();
            }
        }

        const style = document.createElement('style');
        style.textContent = animationCSS;
        document.head.appendChild(style);

        // ── Zarządzanie nadawcami ────────────────────────────────────────

        async function loadSenders() {
            try {
                const resp = await fetch('/api/senders');
                if (!resp.ok) return;
                const senders = await resp.json();
                renderSenderSelect(senders);
                renderSendersList(senders);
            } catch (e) {
                console.error('Błąd ładowania nadawców:', e);
            }
        }

        function renderSenderSelect(senders) {
            const sel = document.getElementById('senderSelect');
            const currentVal = sel.value;
            sel.innerHTML = '<option value="">-- Wybierz nadawcę --</option>';
            senders.forEach(s => {
                const opt = document.createElement('option');
                opt.value = s.id;
                opt.textContent = s.nazwa + (s.miasto ? ` (${s.miasto})` : '');
                sel.appendChild(opt);
            });
            sel.value = currentVal;
        }

        function renderSendersList(senders) {
            const container = document.getElementById('sidebarSendersList');
            if (!container) return;
            if (senders.length === 0) {
                container.innerHTML = '<p style="color:#718096;font-size:14px;">Brak nadawców. Dodaj pierwszego.</p>';
                return;
            }
            container.innerHTML = senders.map(s => `
                <div class="sender-item">
                    <div>
                        <div class="sender-item-name">${escapeHtml(s.nazwa)}</div>
                        <div class="sender-item-detail">${escapeHtml(s.adres || '')}${s.miasto ? ', ' + escapeHtml(s.miasto) : ''}</div>
                    </div>
                    <div class="sender-actions">
                        <button class="btn-edit-sender" onclick="editSender(${s.id})">Edytuj</button>
                        <button class="btn-del-sender" onclick="deleteSender(${s.id})">Usuń</button>
                    </div>
                </div>
            `).join('');
        }

        function escapeHtml(str) {
            return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
        }

        function selectSender() {
            const sel = document.getElementById('senderSelect');
            const id = parseInt(sel.value);
            if (!id) { currentSender = null; return; }
            fetch('/api/senders').then(r => r.json()).then(senders => {
                currentSender = senders.find(s => s.id === id) || null;
            });
        }

        // ── Panel użytkownika (sidebar) ────────────────────────────────

        function openUserPanel() {
            document.getElementById('userSidebar').classList.add('open');
            document.getElementById('sidebarOverlay').classList.add('open');
            loadAccountInfo();
        }

        function closeUserPanel() {
            document.getElementById('userSidebar').classList.remove('open');
            document.getElementById('sidebarOverlay').classList.remove('open');
        }

        function switchSidebarTab(tab, event) {
            document.querySelectorAll('.sidebar-tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.sidebar-tab-content').forEach(c => c.style.display = 'none');
            document.getElementById('sidebarTab-' + tab).style.display = 'block';
            if (event && event.target) event.target.classList.add('active');
        }

        async function loadAccountInfo() {
            try {
                const resp = await fetch('/auth/me');
                if (!resp.ok) return;
                const user = await resp.json();
                const el = document.getElementById('accountEmail');
                if (el) el.textContent = user.email || user.login || '';
                const nameEl = document.getElementById('sidebarUserName');
                if (nameEl) nameEl.textContent = user.display_name || user.email || 'Konto';
            } catch(e) {}
        }

        async function logoutUser() {
            try { await fetch('/auth/logout', { method: 'POST' }); } catch(e) {}
            window.location.href = '/login';
        }

        // ── Modal ustawień ─────────────────────────────────────────────

        async function openSettingsModal() {
            closeUserPanel();
            document.getElementById('settingsModalOverlay').classList.add('open');
            await loadProfileData();
            await loadPlansData();
            applyThemeButtons();
        }

        function closeSettingsModal() {
            document.getElementById('settingsModalOverlay').classList.remove('open');
        }

        // Zamknięcie po kliknięciu w overlay
        document.getElementById('settingsModalOverlay').addEventListener('click', function(e) {
            if (e.target === this) closeSettingsModal();
        });

        function switchSettingsTab(tab, event) {
            document.querySelectorAll('.settings-tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.settings-tab-content').forEach(c => c.classList.remove('active'));
            document.getElementById('settingsTab-' + tab).classList.add('active');
            if (event && event.target) event.target.classList.add('active');
        }

        // ── Profil ──────────────────────────────────────────────────────

        async function loadProfileData() {
            try {
                const resp = await fetch('/api/settings/profile');
                if (!resp.ok) return;
                const d = await resp.json();
                document.getElementById('settingsDisplayName').value = d.display_name || '';
                document.getElementById('settingsEmail').value = d.email || '';
                document.getElementById('profileCreatedAt').textContent = d.created_at ? new Date(d.created_at).toLocaleDateString('pl-PL') : '—';
                document.getElementById('profileLastLogin').textContent = d.last_login ? new Date(d.last_login).toLocaleString('pl-PL') : '—';
                document.getElementById('profilePlan').textContent = d.plan ? d.plan.toUpperCase() : '—';

                // Pasek postępu
                const used = d.letters_used || 0;
                const limit = d.letters_limit || 50;
                const pct = limit > 0 ? Math.min(100, Math.round(used / limit * 100)) : 0;
                document.getElementById('usageText').textContent = `${used} / ${limit} pism`;
                const fill = document.getElementById('usageBarFill');
                fill.style.width = pct + '%';
                fill.className = 'usage-bar-fill' + (pct >= 90 ? ' danger' : pct >= 70 ? ' warn' : '');

                // Toggle powiadomień
                document.getElementById('toggleNotifications').checked = !!d.email_notifications;
            } catch(e) {}
        }

        async function saveDisplayName() {
            const val = document.getElementById('settingsDisplayName').value.trim();
            const msgEl = document.getElementById('displayNameMsg');
            msgEl.className = '';
            msgEl.textContent = '';
            try {
                const resp = await fetch('/api/settings/display-name', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ display_name: val })
                });
                const r = await resp.json();
                if (resp.ok) {
                    msgEl.className = 'settings-success';
                    msgEl.textContent = '✓ Zapisano';
                    const nameEl = document.getElementById('sidebarUserName');
                    if (nameEl) nameEl.textContent = val;
                } else {
                    msgEl.className = 'settings-error';
                    msgEl.textContent = r.error || 'Błąd zapisu';
                }
            } catch(e) {
                msgEl.className = 'settings-error';
                msgEl.textContent = 'Błąd połączenia';
            }
        }

        // ── Hasło ───────────────────────────────────────────────────────

        async function changePassword() {
            ['pwdCurrentErr','pwdNewErr','pwdConfirmErr'].forEach(id => {
                document.getElementById(id).textContent = '';
            });
            const msgEl = document.getElementById('pwdMsg');
            msgEl.textContent = '';

            const currentPwd = document.getElementById('pwdCurrent').value;
            const newPwd = document.getElementById('pwdNew').value;
            const confirmPwd = document.getElementById('pwdConfirm').value;

            let valid = true;
            if (!currentPwd) {
                document.getElementById('pwdCurrentErr').textContent = 'Podaj aktualne hasło';
                valid = false;
            }
            if (newPwd.length < 8) {
                document.getElementById('pwdNewErr').textContent = 'Min. 8 znaków';
                valid = false;
            } else if (!/\d/.test(newPwd)) {
                document.getElementById('pwdNewErr').textContent = 'Musi zawierać cyfrę';
                valid = false;
            }
            if (newPwd !== confirmPwd) {
                document.getElementById('pwdConfirmErr').textContent = 'Hasła nie są identyczne';
                valid = false;
            }
            if (!valid) return;

            try {
                const resp = await fetch('/api/settings/change-password', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ current_password: currentPwd, new_password: newPwd, confirm_password: confirmPwd })
                });
                const r = await resp.json();
                if (resp.ok) {
                    msgEl.style.color = '#27ae60';
                    msgEl.textContent = '✓ Hasło zostało zmienione';
                    document.getElementById('pwdCurrent').value = '';
                    document.getElementById('pwdNew').value = '';
                    document.getElementById('pwdConfirm').value = '';
                } else {
                    msgEl.style.color = '#dc3545';
                    msgEl.textContent = r.error || 'Błąd zmiany hasła';
                }
            } catch(e) {
                msgEl.style.color = '#dc3545';
                msgEl.textContent = 'Błąd połączenia';
            }
        }

        // ── Motyw i powiadomienia ────────────────────────────────────────

        async function setTheme(theme) {
            if (theme === 'dark') {
                document.body.classList.add('dark-mode');
            } else {
                document.body.classList.remove('dark-mode');
            }
            applyThemeButtons();
            const msgEl = document.getElementById('appearanceMsg');
            msgEl.style.color = '';
            try {
                const resp = await fetch('/api/settings/theme', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ theme })
                });
                const r = await resp.json();
                if (resp.ok) {
                    msgEl.style.color = '#27ae60';
                    msgEl.textContent = '✓ Motyw zapisany';
                } else {
                    msgEl.style.color = '#dc3545';
                    msgEl.textContent = r.error || 'Błąd zapisu motywu';
                }
            } catch(e) {
                msgEl.style.color = '#dc3545';
                msgEl.textContent = 'Błąd połączenia';
            }
            setTimeout(() => { msgEl.textContent = ''; }, 3000);
        }

        function applyThemeButtons() {
            const isDark = document.body.classList.contains('dark-mode');
            document.getElementById('btnThemeLight').classList.toggle('active', !isDark);
            document.getElementById('btnThemeDark').classList.toggle('active', isDark);
        }

        async function saveNotifications() {
            const val = document.getElementById('toggleNotifications').checked;
            const msgEl = document.getElementById('appearanceMsg');
            try {
                const resp = await fetch('/api/settings/notifications', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ email_notifications: val })
                });
                const r = await resp.json();
                msgEl.style.color = resp.ok ? '#27ae60' : '#dc3545';
                msgEl.textContent = resp.ok ? '✓ Ustawienie zapisane' : (r.error || 'Błąd zapisu');
            } catch(e) {
                msgEl.style.color = '#dc3545';
                msgEl.textContent = 'Błąd połączenia';
            }
            setTimeout(() => { msgEl.textContent = ''; }, 3000);
        }

        // ── Plany ───────────────────────────────────────────────────────

        async function loadPlansData() {
            try {
                const resp = await fetch('/api/settings/plans');
                if (!resp.ok) return;
                const data = await resp.json();
                const container = document.getElementById('planCards');
                if (!data.plans || !data.plans.length) {
                    container.innerHTML = '<div style="color:#aaa;text-align:center;">Brak planów</div>';
                    return;
                }
                container.innerHTML = data.plans.map(p => `
                    <div class="plan-card ${p.is_current ? 'current' : ''}">
                        ${p.is_current ? '<div class="plan-card-badge">✓ Aktualny</div>' : ''}
                        <div class="plan-card-name">${p.display_name}</div>
                        <div class="plan-card-price">${p.price === 0 ? 'Bezpłatny' : p.price_pln.toFixed(0) + ' zł'}<span>${p.price > 0 ? '/mies.' : ''}</span></div>
                        <div class="plan-card-limit">${p.letters_limit} pism / miesiąc</div>
                        <button class="btn-plan" disabled title="Płatności wkrótce dostępne">
                            ${p.is_current ? 'Aktualny plan' : 'Wybierz plan'}
                        </button>
                    </div>
                `).join('');
            } catch(e) {}
        }

        // ── Inicjalizacja motywu przy starcie ───────────────────────────
        (async function initTheme() {
            try {
                const resp = await fetch('/api/settings/profile');
                if (!resp.ok) return;
                const d = await resp.json();
                if (d.theme === 'dark') document.body.classList.add('dark-mode');
                const nameEl = document.getElementById('sidebarUserName');
                if (nameEl && d.display_name) nameEl.textContent = d.display_name;
            } catch(e) {}
        })();

        // ── Modal nadawcy ──────────────────────────────────────────────

        function openSenderModal(id) {
            editingSenderId = id || null;
            const modal = document.getElementById('senderModal');
            document.getElementById('modalSenderTitle').textContent = id ? 'Edytuj nadawcę' : 'Dodaj nadawcę';
            document.getElementById('senderNazwa').value = '';
            document.getElementById('senderAdres').value = '';
            document.getElementById('senderMiasto').value = '';
            document.getElementById('senderKod').value = '';
            document.getElementById('senderTelefon').value = '';
            document.getElementById('senderEmail').value = '';

            if (id) {
                fetch('/api/senders').then(r => r.json()).then(senders => {
                    const s = senders.find(x => x.id === id);
                    if (s) {
                        document.getElementById('senderNazwa').value = s.nazwa || '';
                        document.getElementById('senderAdres').value = s.adres || '';
                        document.getElementById('senderMiasto').value = s.miasto || '';
                        document.getElementById('senderKod').value = s.kod_pocztowy || '';
                        document.getElementById('senderTelefon').value = s.telefon || '';
                        document.getElementById('senderEmail').value = s.email || '';
                    }
                });
            }
            modal.classList.add('open');
        }

        function closeSenderModal() {
            document.getElementById('senderModal').classList.remove('open');
            editingSenderId = null;
        }

        async function saveSender() {
            const nazwa = document.getElementById('senderNazwa').value.trim();
            if (!nazwa) { alert('Pole Nazwa jest wymagane!'); return; }
            const body = {
                nazwa,
                adres: document.getElementById('senderAdres').value.trim(),
                miasto: document.getElementById('senderMiasto').value.trim(),
                kod_pocztowy: document.getElementById('senderKod').value.trim(),
                telefon: document.getElementById('senderTelefon').value.trim(),
                email: document.getElementById('senderEmail').value.trim()
            };
            const url = editingSenderId ? `/api/senders/${editingSenderId}` : '/api/senders';
            const method = editingSenderId ? 'PUT' : 'POST';
            try {
                const resp = await fetch(url, {
                    method,
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(body)
                });
                const result = await resp.json();
                if (resp.ok) {
                    closeSenderModal();
                    await loadSenders();
                } else {
                    alert('Błąd: ' + (result.error || 'Nieznany błąd'));
                }
            } catch(e) {
                alert('Nie udało się połączyć z serwerem.');
            }
        }

        async function editSender(id) {
            closeUserPanel();
            openSenderModal(id);
        }

        async function deleteSender(id) {
            if (!confirm('Usunąć tego nadawcę?')) return;
            try {
                const resp = await fetch(`/api/senders/${id}`, { method: 'DELETE' });
                if (resp.ok) {
                    if (currentSender && currentSender.id === id) {
                        currentSender = null;
                        document.getElementById('senderSelect').value = '';
                    }
                    await loadSenders();
                } else {
                    const r = await resp.json();
                    alert('Błąd: ' + (r.error || 'Nieznany błąd'));
                }
            } catch(e) {
                alert('Nie udało się połączyć z serwerem.');
            }
        }

        // ── Historia pism ──────────────────────────────────────────────

        var currentPreviewId = null;  // var żeby było dostępne jako window.currentPreviewId w onclick atrybutach

        function getHistoryIcon(doc_type, subtype) {
            if (doc_type === 'komornicze' || (subtype || '').toLowerCase().includes('komorni')) return '⚖️';
            const st = (subtype || '').toLowerCase();
            if (st.includes('szkol') || st.includes('szkoł')) return '🏫';
            if (st.includes('uczel')) return '🎓';
            if (st.includes('bank') || st.includes('kredyt')) return '🏦';
            if (st.includes('sad') || st.includes('sąd')) return '⚖️';
            return HISTORY_ICONS[doc_type] || HISTORY_ICONS['default'];
        }

        function formatHistoryDate(isoStr) {
            if (!isoStr) return '—';
            const d = new Date(isoStr);
            const dd = String(d.getDate()).padStart(2, '0');
            const mm = String(d.getMonth() + 1).padStart(2, '0');
            const yyyy = d.getFullYear();
            const hh = String(d.getHours()).padStart(2, '0');
            const min = String(d.getMinutes()).padStart(2, '0');
            return `${dd}.${mm}.${yyyy} ${hh}:${min}`;
        }

        function openHistory() {
            document.getElementById('view-main').style.display = 'none';
            const vh = document.getElementById('view-history');
            vh.style.display = 'block';
            vh.classList.add('active');
            loadHistory();
        }

        function closeHistory() {
            document.getElementById('view-history').style.display = 'none';
            document.getElementById('view-history').classList.remove('active');
            document.getElementById('view-main').style.display = 'block';
        }

        async function loadHistory() {
            const listEl = document.getElementById('historyList');
            const badgeEl = document.getElementById('historyUsageBadge');
            listEl.innerHTML = '<div class="history-empty"><div class="history-empty-icon">⏳</div>Ładowanie…</div>';
            try {
                const [histResp, profileResp] = await Promise.all([
                    fetch('/api/history'),
                    fetch('/api/settings/profile')
                ]);
                if (profileResp.ok) {
                    const p = await profileResp.json();
                    badgeEl.textContent = `Wykorzystano ${p.letters_used}/${p.letters_limit} pism`;
                }
                if (!histResp.ok) {
                    listEl.innerHTML = '<div class="history-empty"><div class="history-empty-icon">⚠️</div>Błąd ładowania historii.</div>';
                    return;
                }
                const data = await histResp.json();
                const letters = data.history || data.letters || [];
                if (!letters.length) {
                    listEl.innerHTML = '<div class="history-empty"><div class="history-empty-icon">📭</div>Nie masz jeszcze żadnych wygenerowanych pism.</div>';
                    return;
                }
                listEl.innerHTML = '<div class="history-list">' + letters.map(l => `
                    <div class="history-card" id="hcard-${l.id}">
                        <div class="history-card-icon">${getHistoryIcon(l.document_type, l.subtype)}</div>
                        <div class="history-card-info">
                            <div class="history-card-title" title="${(l.title || '').replace(/"/g,'&quot;')}">${l.title || 'Bez tytułu'}</div>
                            <div class="history-card-meta">
                                ${l.recipient_name ? `Do: ${l.recipient_name} &nbsp;•&nbsp; ` : ''}${formatHistoryDate(l.created_at)}
                            </div>
                        </div>
                        <div class="history-card-actions">
                            <button class="btn-hist btn-hist-preview" onclick="previewLetter(${l.id})">👁️ Podgląd</button>
                            <button class="btn-hist btn-hist-doc" onclick="downloadFromHistory(${l.id}, 'doc')">📄 DOC</button>
                            <button class="btn-hist btn-hist-pdf" onclick="downloadFromHistory(${l.id}, 'pdf')">📃 PDF</button>
                            <button class="btn-hist btn-hist-del" onclick="deleteFromHistory(${l.id})">🗑️ Usuń</button>
                        </div>
                    </div>
                `).join('') + '</div>';
            } catch(e) {
                console.error('loadHistory error:', e);
                listEl.innerHTML = `<div class="history-empty"><div class="history-empty-icon">⚠️</div>Błąd: ${e.message || 'Nie można połączyć się z serwerem'}.<br><small style="color:#aaa;">Sprawdź czy serwer działa i odśwież stronę.</small></div>`;
            }
        }

        async function previewLetter(id) {
            currentPreviewId = id;
            document.getElementById('previewModalTitle').textContent = 'Ładowanie…';
            document.getElementById('previewModalBody').innerHTML = '<div style="text-align:center;padding:40px;color:#aaa;">⏳ Ładowanie treści pisma…</div>';
            document.getElementById('previewModalOverlay').classList.add('open');
            try {
                const resp = await fetch(`/api/history/${id}`);
                if (!resp.ok) {
                    document.getElementById('previewModalBody').innerHTML = '<div style="text-align:center;padding:40px;color:#c0392b;">Nie udało się załadować pisma.</div>';
                    return;
                }
                const data = await resp.json();
                const letter = data.letter || data;
                document.getElementById('previewModalTitle').textContent = letter.title || 'Pismo';
                document.getElementById('previewModalBody').innerHTML = letter.html_content || '<em>Brak treści</em>';
            } catch(e) {
                document.getElementById('previewModalBody').innerHTML = '<div style="text-align:center;padding:40px;color:#c0392b;">Błąd połączenia.</div>';
            }
        }

        function closePreviewModal() {
            document.getElementById('previewModalOverlay').classList.remove('open');
            currentPreviewId = null;
        }

        document.addEventListener('DOMContentLoaded', function() {
            var overlayEl = document.getElementById('previewModalOverlay');
            if (overlayEl) {
                overlayEl.addEventListener('click', function(e) {
                    if (e.target === this) closePreviewModal();
                });
            }
        });

        async function downloadFromHistory(id, format) {
            if (!id) return;
            try {
                const url = `/api/history/${id}/download-${format}`;
                const resp = await fetch(url, { method: 'POST' });
                if (!resp.ok) {
                    const r = await resp.json().catch(() => ({}));
                    showToast('Błąd pobierania: ' + (r.error || resp.statusText), 'error');
                    return;
                }
                const blob = await resp.blob();
                const ext = format === 'pdf' ? 'pdf' : 'docx';
                const a = document.createElement('a');
                a.href = URL.createObjectURL(blob);
                a.download = `pismo_${id}.${ext}`;
                a.click();
                URL.revokeObjectURL(a.href);
            } catch(e) {
                showToast('Błąd pobierania pliku.', 'error');
            }
        }

        async function deleteFromHistory(id) {
            if (!confirm('Czy na pewno chcesz usunąć to pismo z historii?')) return;
            try {
                const resp = await fetch(`/api/history/${id}`, { method: 'DELETE' });
                if (resp.ok) {
                    const card = document.getElementById(`hcard-${id}`);
                    if (card) card.remove();
                    showToast('Pismo usunięte.', 'success');
                    // Jeśli lista pusta - pokaż komunikat
                    const list = document.querySelector('.history-list');
                    if (list && !list.children.length) {
                        document.getElementById('historyList').innerHTML = '<div class="history-empty"><div class="history-empty-icon">📭</div>Nie masz jeszcze żadnych wygenerowanych pism.</div>';
                    }
                } else {
                    const r = await resp.json().catch(() => ({}));
                    showToast('Błąd: ' + (r.error || 'Nie udało się usunąć'), 'error');
                }
            } catch(e) {
                showToast('Błąd połączenia z serwerem.', 'error');
            }
        }

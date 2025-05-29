document.addEventListener('DOMContentLoaded', function() {
    // DOM elements
    const ratingSquares = document.querySelectorAll('.rating-square');
    const npsScoreInput = document.getElementById('npsScore');
    const ratingError = document.getElementById('ratingError');
    const submitBtn = document.getElementById('submitBtn');
    const surveyForm = document.getElementById('surveyForm');

    let selectedRating = null;

    // Initialize rating squares
    ratingSquares.forEach((square, index) => {
        const value = index; // Use index directly (0-10)

        // Add click event - simple and direct
        square.addEventListener('click', function() {
            selectRating(value);
        });

        // Add hover effects
        square.addEventListener('mouseenter', function() {
            if (selectedRating === null) {
                square.classList.add('hover');
            }
        });

        square.addEventListener('mouseleave', function() {
            square.classList.remove('hover');
        });

        // Make squares focusable for accessibility
        square.setAttribute('tabindex', '0');
        square.setAttribute('role', 'button');
        square.setAttribute('aria-label', `Avaliar ${value} de 10`);
    });

    function selectRating(value) {
        selectedRating = value;
        npsScoreInput.value = value;

        // Update visual state
        ratingSquares.forEach((square, index) => {
            square.classList.remove('selected', 'hover');
            if (index === value) {
                square.classList.add('selected');
            }
        });

        // Hide error message
        if (ratingError) {
            ratingError.style.display = 'none';
        }
    }

    // Form submission handler
    surveyForm.addEventListener('submit', function(e) {
        if (!validateForm()) {
            e.preventDefault();
        } else {
            showLoadingState();
        }
    });

    function validateForm() {
        if (selectedRating === null) {
            ratingError.style.display = 'block';
            ratingError.textContent = 'Por favor, selecione uma avaliação antes de continuar';
            return false;
        }
        return true;
    }

    function showLoadingState() {
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Enviando...';
    }
});
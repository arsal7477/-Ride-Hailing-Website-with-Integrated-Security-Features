document.addEventListener('DOMContentLoaded', function() {
    const themeToggle = document.getElementById('theme-toggle');
    const htmlElement = document.documentElement;
    
    // Check for saved theme preference or use preferred color scheme
    const savedTheme = localStorage.getItem('theme') || 
                      (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
    htmlElement.setAttribute('data-theme', savedTheme);
    
    // Set initial icon visibility
    updateIcons(savedTheme);
    
    // Toggle theme on button click
    themeToggle.addEventListener('click', () => {
        const currentTheme = htmlElement.getAttribute('data-theme');
        const newTheme = currentTheme === 'light' ? 'dark' : 'light';
        
        htmlElement.setAttribute('data-theme', newTheme);
        localStorage.setItem('theme', newTheme);
        updateIcons(newTheme);
    });
    
    function updateIcons(theme) {
        const lightIcons = document.querySelectorAll('.light-icon');
        const darkIcons = document.querySelectorAll('.dark-icon');
        
        if (theme === 'light') {
            lightIcons.forEach(icon => icon.style.display = 'inline-block');
            darkIcons.forEach(icon => icon.style.display = 'none');
        } else {
            lightIcons.forEach(icon => icon.style.display = 'none');
            darkIcons.forEach(icon => icon.style.display = 'inline-block');
        }
    }
});
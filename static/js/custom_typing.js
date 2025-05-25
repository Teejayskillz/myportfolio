document.addEventListener('DOMContentLoaded', function() {
    // The text you want to type
    var textToType = "At Lagos Web Dev, we help Businesses grow online with expert web development and SEO services. From custom Django web applications to responsive WordPress websites and Shopify e-commerce stores, we build solutions that drive traffic, improve visibility, and generate results. Explore our portfolio to see what we’ve built.";

    var options = {
        strings: [textToType],
        typeSpeed: 30,
        startDelay: 500,
        showCursor: true,
        cursorChar: '|',
        loop: false,
        onComplete: function(self) {
            self.cursor.style.display = 'none';
            document.getElementById('projects-button').style.display = 'inline-block';
        }
    };

    var typed = new Typed('#typing-text', options);
});
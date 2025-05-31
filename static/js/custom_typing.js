document.addEventListener('DOMContentLoaded', function() {
    // The text you want to type
    var textToType = "At Lagos Web Dev, we specialize in helping businesses grow online. As leading web developers in Lagos, we offer expert web development and SEO services designed to enhance your digital presence. From custom Django web applications to responsive WordPress websites and powerful Shopify e-commerce stores, we build solutions that not only drive traffic and improve search visibility but also generate tangible results for your business. Explore our portfolio to see the successful web development projects we've delivered for various clients across Lagos and beyond.";

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
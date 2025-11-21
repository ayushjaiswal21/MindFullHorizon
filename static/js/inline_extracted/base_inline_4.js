
        function googleTranslateElementInit() {
          // Limit languages to avoid huge dropdown and avoid layout shift
          // adjust includedLanguages list to the languages you want visible: hi (Hindi), bn (Bengali), te (Telugu), mr (Marathi), en (English)
          new google.translate.TranslateElement({
                        pageLanguage: 'en',
                        layout: google.translate.TranslateElement.InlineLayout.SIMPLE,
                        autoDisplay: false,
                        includedLanguages: 'hi,bn,te,mr,en',
                        multilanguagePage: true
                    }, 'google_translate_element');
        
          // When Google inserts the widget it sometimes mutates the DOM and pushes elements.
          // We ensure the wrapper has a fixed width so it does not push other nav buttons.
          const wrapper = document.getElementById('google-translate-wrapper');
          if (wrapper) wrapper.style.width = wrapper.style.width || '180px';
        
          // small defensive reposition if google injects banner frame
          setTimeout(() => {
            // hide the auto banner if it appears (prevents layout shift)
            const iframe = document.querySelector('.goog-te-banner-frame.skiptranslate');
            if (iframe) iframe.style.display = 'none';
          }, 500);
        }    
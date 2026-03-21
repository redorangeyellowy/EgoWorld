document.addEventListener('DOMContentLoaded', () => {
  const navLinks = Array.from(document.querySelectorAll('.nav-link'));
  const sections = navLinks
    .map((link) => document.querySelector(link.getAttribute('href')))
    .filter(Boolean);

  if ('IntersectionObserver' in window && sections.length > 0) {
    const linkById = new Map(
      navLinks.map((link) => [link.getAttribute('href').slice(1), link])
    );

    const observer = new IntersectionObserver(
      (entries) => {
        const visibleEntries = entries
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => {
            // 섹션의 중심이 뷰포트 중심에 가까운 것을 우선 선택
            const aCenter = a.boundingClientRect.top + a.boundingClientRect.height / 2;
            const bCenter = b.boundingClientRect.top + b.boundingClientRect.height / 2;
            const viewportCenter = window.innerHeight / 2;
            const aDistance = Math.abs(aCenter - viewportCenter);
            const bDistance = Math.abs(bCenter - viewportCenter);
            return aDistance - bDistance;
          });

        if (visibleEntries.length === 0) {
          return;
        }

        const activeId = visibleEntries[0].target.id;
        navLinks.forEach((link) => link.classList.remove('is-active'));

        const activeLink = linkById.get(activeId);
        if (activeLink) {
          activeLink.classList.add('is-active');
        }
      },
      {
        rootMargin: '-5% 0px -80% 0px',
        threshold: [0.1, 0.3, 0.6]
      }
    );

    sections.forEach((section) => observer.observe(section));
  }

  // Immediate nav-link active style on click (e.g. results / bibtex 메뉴 클릭 시 언더라인 적용)
  navLinks.forEach((link) => {
    link.addEventListener('click', () => {
      navLinks.forEach((l) => l.classList.remove('is-active'));
      link.classList.add('is-active');
    });
  });

  const titleHighlightRoot = document.querySelector('[data-title-highlight]');
  if (titleHighlightRoot) {
    const titleText = titleHighlightRoot.querySelector('[data-title-highlight-text]');
    const effectWrapper = titleHighlightRoot.querySelector('[data-title-highlight-effect]');

    const clipRectToBounds = (rect, bounds) => {
      const left = Math.max(rect.left, bounds.left);
      const top = Math.max(rect.top, bounds.top);
      const right = Math.min(rect.right, bounds.right);
      const bottom = Math.min(rect.bottom, bounds.bottom);

      if (right <= left || bottom <= top) {
        return null;
      }

      return {
        left,
        top,
        width: right - left,
        height: bottom - top
      };
    };

    const clearTitleHighlight = () => {
      if (!effectWrapper) {
        return;
      }

      effectWrapper.style.webkitMaskImage = 'linear-gradient(transparent, transparent)';
      effectWrapper.style.webkitMaskSize = '0 0';
      effectWrapper.style.webkitMaskPosition = '0 0';
      effectWrapper.style.webkitMaskRepeat = 'no-repeat';
      effectWrapper.style.maskImage = 'linear-gradient(transparent, transparent)';
      effectWrapper.style.maskSize = '0 0';
      effectWrapper.style.maskPosition = '0 0';
      effectWrapper.style.maskRepeat = 'no-repeat';

      titleHighlightRoot
        .querySelectorAll('.publication-title-custom-select')
        .forEach((element) => element.remove());
    };

    const updateTitleHighlight = () => {
      if (!titleText || !effectWrapper) {
        return;
      }

      const selection = window.getSelection();
      if (!selection || selection.rangeCount === 0 || selection.isCollapsed) {
        clearTitleHighlight();
        return;
      }

      const range = selection.getRangeAt(0);
      const anchorInTitle = Boolean(selection.anchorNode && titleText.contains(selection.anchorNode));
      const focusInTitle = Boolean(selection.focusNode && titleText.contains(selection.focusNode));
      const intersectsTitle =
        (anchorInTitle && focusInTitle) ||
        (typeof range.intersectsNode === 'function' && range.intersectsNode(titleText));

      if (!intersectsTitle || !anchorInTitle || !focusInTitle) {
        clearTitleHighlight();
        return;
      }

      const rootRect = titleHighlightRoot.getBoundingClientRect();
      const effectRect = effectWrapper.getBoundingClientRect();
      const titleRect = titleText.getBoundingClientRect();
      const rects = Array.from(range.getClientRects())
        .map((rect) => clipRectToBounds(rect, titleRect))
        .filter((rect) => {
          return rect && rect.width > 0 && rect.height > 0;
        })
        .map((rect) => ({
          rawLeft: rect.left,
          rawTop: rect.top,
          rawWidth: rect.width,
          rawHeight: rect.height
        }))
        .map((rect) => {
          const verticalInset = Math.min(10, rect.rawHeight * 0.14);
          const horizontalInset = Math.min(2, rect.rawWidth * 0.01);
          const horizontalPadding = Math.min(14, Math.max(8, rect.rawWidth * 0.035));
          const left = rect.rawLeft + horizontalInset / 2 - horizontalPadding / 2;
          const top = rect.rawTop + verticalInset / 2;
          const width = Math.max(0, rect.rawWidth - horizontalInset + horizontalPadding);
          const height = Math.max(0, rect.rawHeight - verticalInset);

          return {
            maskX: Math.max(0, left - effectRect.left),
            maskY: Math.max(0, top - effectRect.top),
            x: Math.max(0, left - rootRect.left),
            y: Math.max(0, top - rootRect.top),
            width,
            height
          };
        });

      if (rects.length === 0) {
        clearTitleHighlight();
        return;
      }

      const maskSvg = `
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${effectRect.width} ${effectRect.height}">
          ${rects
            .map((rect) => {
              const radius = Math.min(12, rect.width / 2, rect.height / 2);
              return `<rect fill="white" x="${rect.maskX}" y="${rect.maskY}" width="${rect.width}" height="${rect.height}" rx="${radius}" ry="${radius}" />`;
            })
            .join('')}
        </svg>
      `;
      const maskImage = `url("data:image/svg+xml,${encodeURIComponent(maskSvg)}")`;
      const maskSize = `${Math.ceil(effectRect.width)}px ${Math.ceil(effectRect.height)}px`;

      effectWrapper.style.webkitMaskImage = maskImage;
      effectWrapper.style.webkitMaskSize = maskSize;
      effectWrapper.style.webkitMaskPosition = '0 0';
      effectWrapper.style.webkitMaskRepeat = 'no-repeat';
      effectWrapper.style.maskImage = maskImage;
      effectWrapper.style.maskSize = maskSize;
      effectWrapper.style.maskPosition = '0 0';
      effectWrapper.style.maskRepeat = 'no-repeat';

      titleHighlightRoot
        .querySelectorAll('.publication-title-custom-select')
        .forEach((element) => element.remove());

      rects.forEach((rect) => {
        const highlight = document.createElement('span');
        highlight.className = 'publication-title-custom-select';
        highlight.style.left = `${rect.x}px`;
        highlight.style.top = `${rect.y}px`;
        highlight.style.width = `${rect.width}px`;
        highlight.style.height = `${rect.height}px`;
        titleHighlightRoot.appendChild(highlight);
      });
    };

    document.addEventListener('selectionchange', updateTitleHighlight);
    window.addEventListener('resize', clearTitleHighlight);
  }

  const analysisCarousel = document.querySelector('[data-analysis-carousel]');
  if (analysisCarousel) {
    const track = analysisCarousel.querySelector('[data-analysis-track]');
    const prevButton = analysisCarousel.querySelector('[data-analysis-prev]');
    const nextButton = analysisCarousel.querySelector('[data-analysis-next]');
    const counter = document.querySelector('[data-analysis-counter]');
    const dotsContainer = document.querySelector('[data-analysis-dots]');
    const slides = track ? Array.from(track.querySelectorAll('.analysis-slide')) : [];
    let currentIndex = 0;

    const renderAnalysisCarousel = () => {
      if (!track || slides.length === 0) {
        return;
      }

      track.style.transform = `translateX(-${currentIndex * 100}%)`;

      if (prevButton) {
        prevButton.disabled = currentIndex === 0;
      }

      if (nextButton) {
        nextButton.disabled = currentIndex === slides.length - 1;
      }

      if (counter) {
        counter.textContent = `${currentIndex + 1} / ${slides.length}`;
      }

      if (dotsContainer) {
        Array.from(dotsContainer.children).forEach((dot, index) => {
          dot.classList.toggle('is-active', index === currentIndex);
        });
      }
    };

    if (dotsContainer) {
      slides.forEach((slide, index) => {
        const dot = document.createElement('button');
        dot.type = 'button';
        dot.className = 'analysis-dot';
        dot.setAttribute('aria-label', `Go to analysis ${index + 1}`);
        dot.addEventListener('click', () => {
          currentIndex = index;
          renderAnalysisCarousel();
        });
        dotsContainer.appendChild(dot);
      });
    }

    if (prevButton) {
      prevButton.addEventListener('click', () => {
        if (currentIndex > 0) {
          currentIndex -= 1;
          renderAnalysisCarousel();
        }
      });
    }

    if (nextButton) {
      nextButton.addEventListener('click', () => {
        if (currentIndex < slides.length - 1) {
          currentIndex += 1;
          renderAnalysisCarousel();
        }
      });
    }

    renderAnalysisCarousel();
  }

  const copyButton = document.querySelector('[data-copy-target]');
  if (!copyButton) {
    return;
  }

  copyButton.addEventListener('click', async () => {
    const targetId = copyButton.getAttribute('data-copy-target');
    const target = targetId ? document.getElementById(targetId) : null;
    if (!target) {
      return;
    }

    try {
      await navigator.clipboard.writeText(target.textContent);
      const previousText = copyButton.textContent;
      copyButton.textContent = 'Copied';
      copyButton.classList.add('is-copied');

      window.setTimeout(() => {
        copyButton.textContent = previousText;
        copyButton.classList.remove('is-copied');
      }, 1600);
    } catch (error) {
      copyButton.textContent = 'Copy failed';
      window.setTimeout(() => {
        copyButton.textContent = 'Copy';
      }, 1600);
    }
  });
});

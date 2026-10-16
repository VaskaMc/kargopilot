"""Embeds the Dual-Hosting modal and connection script into showcase.html and index.html."""

def main():
    with open('web_panel/templates/components/dual_hosting_modal.html', 'r', encoding='utf-8') as f:
        modal_content = f.read()

    with open('web_panel/templates/showcase.html', 'r', encoding='utf-8') as f:
        showcase_content = f.read()

    target = '</body>'
    if target not in showcase_content:
        raise ValueError("Target </body> not found in showcase.html")

    replacement = '<script src="assets/kargopilot-connection.js"></script>\n\n' + modal_content + '\n</body>'
    updated_showcase = showcase_content.replace(target, replacement, 1)

    with open('web_panel/templates/showcase.html', 'w', encoding='utf-8') as f:
        f.write(updated_showcase)

    with open('index.html', 'w', encoding='utf-8') as f:
        f.write(updated_showcase)

    print("SUCCESS: Successfully injected Dual-Hosting modal into showcase.html and index.html")

if __name__ == '__main__':
    main()

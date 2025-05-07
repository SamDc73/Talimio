import { useState } from "react";
import { CodeBlock } from "./code-block";
import { Button } from "./button";

const SAMPLE_CODE = {
  javascript: `// A simple JavaScript function
function greet(name) {
  return \`Hello, \${name}!\`;
}

// Call the function
console.log(greet("World"));`,

  python: `# A simple Python function
def greet(name):
    return f"Hello, {name}!"

# Call the function
print(greet("World"))`,

  jsx: `// A React component
import { useState } from 'react';

export function Counter() {
  const [count, setCount] = useState(0);

  return (
    <div className="counter">
      <h2>Count: {count}</h2>
      <button onClick={() => setCount(count + 1)}>
        Increment
      </button>
    </div>
  );
}`,

  css: `/* Catppuccin Latte styles */
.container {
  background-color: #eff1f5;
  color: #4c4f69;
  padding: 1rem;
  border-radius: 0.5rem;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.button {
  background-color: #1e66f5;
  color: #ffffff;
  border: none;
  padding: 0.5rem 1rem;
  border-radius: 0.25rem;
  cursor: pointer;
  transition: background-color 0.2s;
}

.button:hover {
  background-color: #1e66f5cc;
}`,
};

// Example of code with highlighted lines and words
const HIGHLIGHTED_CODE = `// This is a function with highlighted parts
function calculateTotal(items) {
  // This line will be highlighted
  return items
    .map(item => item.price * item.quantity)
    .reduce((total, itemTotal) => total + itemTotal, 0);
}

// This word will be highlighted
const total = calculateTotal(cart);
console.log(\`Your total is: \${total}\`);`;

export function CodeBlockTest() {
  const [language, setLanguage] = useState("javascript");
  const [showHighlighted, setShowHighlighted] = useState(false);

  return (
    <div className="p-6 max-w-3xl mx-auto">
      <h1 className="text-2xl font-bold mb-4">Code Block Test</h1>

      <div className="flex gap-2 mb-4">
        {Object.keys(SAMPLE_CODE).map((lang) => (
          <Button
            key={lang}
            onClick={() => {
              setLanguage(lang);
              setShowHighlighted(false);
            }}
            variant={language === lang && !showHighlighted ? "default" : "outline"}
          >
            {lang}
          </Button>
        ))}
        <Button onClick={() => setShowHighlighted(true)} variant={showHighlighted ? "default" : "outline"}>
          Highlighted
        </Button>
      </div>

      {showHighlighted ? (
        <div>
          <h2 className="text-lg font-semibold mb-2">Code with Highlighting</h2>
          <pre className="bg-[#eff1f5] p-4 rounded-md overflow-x-auto text-sm font-mono">
            <code className="language-javascript">{HIGHLIGHTED_CODE}</code>
          </pre>
          <p className="mt-4 text-sm text-zinc-500">
            Note: Line and word highlighting requires rehype-pretty-code to be properly configured in MDX processing.
            This is just a visual example.
          </p>
        </div>
      ) : (
        <CodeBlock code={SAMPLE_CODE[language]} language={language} />
      )}
    </div>
  );
}

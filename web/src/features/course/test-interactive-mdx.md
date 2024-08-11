# Test Interactive MDX Lesson

This is a test lesson to verify interactive components work.

## Basic Counter Example

Let's test a simple interactive counter:

export function Counter() {
  const [count, setCount] = React.useState(0);
  
  return (
    <div style={{
      padding: '24px',
      background: '#f8fafc',
      borderRadius: '12px',
      margin: '24px 0',
      textAlign: 'center'
    }}>
      <h3 style={{ margin: '0 0 16px 0', color: '#374151' }}>
        Interactive Counter Demo
      </h3>
      <div style={{ fontSize: '48px', fontWeight: 'bold', color: '#3b82f6', marginBottom: '16px' }}>
        {count}
      </div>
      <div style={{ display: 'flex', gap: '12px', justifyContent: 'center' }}>
        <button 
          onClick={() => setCount(count - 1)}
          style={{
            padding: '8px 16px',
            background: '#ef4444',
            color: 'white',
            border: 'none',
            borderRadius: '6px',
            cursor: 'pointer',
            fontSize: '16px'
          }}
        >
          Decrease
        </button>
        <button 
          onClick={() => setCount(0)}
          style={{
            padding: '8px 16px',
            background: '#64748b',
            color: 'white',
            border: 'none',
            borderRadius: '6px',
            cursor: 'pointer',
            fontSize: '16px'
          }}
        >
          Reset
        </button>
        <button 
          onClick={() => setCount(count + 1)}
          style={{
            padding: '8px 16px',
            background: '#10b981',
            color: 'white',
            border: 'none',
            borderRadius: '6px',
            cursor: 'pointer',
            fontSize: '16px'
          }}
        >
          Increase
        </button>
      </div>
    </div>
  );
}

<Counter />

## Math Example with KaTeX

Here's an equation: $E = mc^2$

And a display equation:

$$
\int_{0}^{\infty} e^{-x^2} dx = \frac{\sqrt{\pi}}{2}
$$

## Interactive Slider Example

export function SliderDemo() {
  const [value, setValue] = React.useState(50);
  
  return (
    <div style={{
      padding: '24px',
      background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
      borderRadius: '12px',
      margin: '24px 0',
      color: 'white'
    }}>
      <h3 style={{ margin: '0 0 16px 0' }}>Adjust the Value</h3>
      <div style={{ fontSize: '36px', fontWeight: 'bold', marginBottom: '16px' }}>
        {value}%
      </div>
      <input
        type="range"
        min="0"
        max="100"
        value={value}
        onChange={(e) => setValue(Number(e.target.value))}
        style={{
          width: '100%',
          height: '8px',
          borderRadius: '4px',
          background: 'rgba(255, 255, 255, 0.3)',
          outline: 'none',
          cursor: 'pointer'
        }}
      />
      <div style={{
        marginTop: '16px',
        height: '20px',
        background: 'rgba(255, 255, 255, 0.2)',
        borderRadius: '10px',
        overflow: 'hidden'
      }}>
        <div style={{
          width: `${value}%`,
          height: '100%',
          background: 'rgba(255, 255, 255, 0.8)',
          transition: 'width 0.3s ease'
        }} />
      </div>
    </div>
  );
}

<SliderDemo />

## Summary

If you can see the interactive components above working (counter buttons, slider), then the interactive MDX integration is successful!
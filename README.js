import { useState, useEffect, useRef } from 'react'

export default function TerminalProfile() {
  const [input, setInput] = useState('')
  const [output, setOutput] = useState<string[]>([])
  const [cursorVisible, setCursorVisible] = useState(true)
  const inputRef = useRef<HTMLInputElement>(null)

  // Blinking cursor effect
  useEffect(() => {
    const interval = setInterval(() => {
      setCursorVisible(prev => !prev)
    }, 500)
    return () => clearInterval(interval)
  }, [])

  // Focus input on mount
  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.focus()
    }
  }, [])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (input.trim().toLowerCase() === 'whomai') {
      setOutput([
        'Name: John Doe',
        'Role: Full Stack Developer',
        'Skills: React, Node.js, TypeScript',
        'Location: San Francisco, CA',
        'Interests: Open source, hiking, photography',
        'GitHub: github.com/johndoe',
        'LinkedIn: linkedin.com/in/johndoe'
      ])
    } else {
      setOutput([`Command not found: ${input}. Try 'whomai'`])
    }
    setInput('')
  }

  return (
    <div className="bg-black text-green-400 p-4 rounded-lg font-mono max-w-2xl mx-auto">
      <div className="mb-4">
        <p>Welcome to my terminal profile!</p>
        <p>Type 'whomai' to learn more about me.</p>
      </div>

      {output.map((line, i) => (
        <p key={i} className="mb-1">{line}</p>
      ))}

      <form onSubmit={handleSubmit} className="flex items-center">
        <span className="mr-2">$</span>
        <div className="relative flex-grow">
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            className="bg-transparent border-none outline-none text-green-400 w-full"
          />
          <span 
            className={`absolute left-0 top-0 h-5 w-2 bg-green-400 ${cursorVisible ? 'opacity-100' : 'opacity-0'}`}
            style={{ left: `${input.length * 0.6}ch` }}
          />
        </div>
      </form>
    </div>
  )
}



<h3 align="left">Common Tools</h3>

###

<div align="left">
  <img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/html5/html5-original.svg" height="40" alt="html5 logo"  />
  <img width="12" />
  <img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/css3/css3-original.svg" height="40" alt="css3 logo"  />
  <img width="12" />
  <img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/javascript/javascript-original.svg" height="40" alt="javascript logo"  />
  <img width="12" />
  <img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/nodejs/nodejs-original.svg" height="40" alt="nodejs logo"  />
  <img width="12" />
  <img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/python/python-original.svg" height="40" alt="python logo"  />
  <img width="12" />
  <img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/linux/linux-original.svg" height="40" alt="linux logo"  />
  <img width="12" />
  <img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/debian/debian-original.svg" height="40" alt="debian logo"  />
  <img width="12" />
  <img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/azure/azure-original.svg" height="40" alt="azure logo"  />
  <img width="12" />
  <img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/sqlite/sqlite-original.svg" height="40" alt="sqlite logo"  />
  <img width="12" />
  <img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/vscode/vscode-original.svg" height="40" alt="vscode logo"  />
  <img width="12" />
  <img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/cplusplus/cplusplus-original.svg" height="40" alt="cplusplus logo"  />
  <img width="12" />
  <img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/microsoftsqlserver/microsoftsqlserver-plain.svg" height="40" alt="microsoftsqlserver logo"  />
</div>

###

<h3 align="left">Daily Stats</h3>

###

<div align="center">
  <img src="https://streak-stats.demolab.com?user=uzairshahidgithub&locale=en&mode=daily&theme=dark&hide_border=false&border_radius=5&order=3" height="220" alt="streak graph"  />
</div>

###

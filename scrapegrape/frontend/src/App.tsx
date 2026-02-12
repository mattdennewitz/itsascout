import './App.css'
import { DataTable } from './datatable/table'
import { columns, type Publisher } from './datatable/columns'
import { useEffect, useState } from 'react'

function App() {
  const [data, setData] = useState<Publisher[]>([])

  useEffect(() => {
    const scriptElement = document.getElementById('publisher-data')
    if (scriptElement && scriptElement.textContent) {
      try {
        const publisherData = JSON.parse(scriptElement.textContent) as Publisher[]
        setData(publisherData)
      } catch (error) {
        console.error('Failed to parse publisher data:', error)
      }
    }
  }, [])

  return (
    <div className="container mx-auto py-10">
      <h1 className="text-2xl mb-4">Publishers</h1>
      <DataTable columns={columns} data={data} />
    </div>
  )
}

export default App

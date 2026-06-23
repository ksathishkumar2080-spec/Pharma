"use client";
import {useEffect,useState} from "react";
import {motion,AnimatePresence} from "motion/react";

const API=process.env.NEXT_PUBLIC_API_URL||"http://localhost:8000";
type H={id:string,name:string,specialty?:string,kol_tier?:string,influence_score?:number,institution?:string,children?:H[]};

const BD:Record<string,string>={
  national:"bg-yellow-400/20 text-yellow-300 border-yellow-400/40",
  regional:"bg-blue-400/20 text-blue-300 border-blue-400/40",
  local:"bg-gray-400/20 text-gray-300 border-gray-400/40",
  emerging:"bg-green-400/20 text-green-300 border-green-400/40",
};
const TS:Record<string,string>={
  national:"bg-yellow-500 text-black",
  regional:"bg-blue-500 text-white",
  local:"bg-gray-600 text-white",
  emerging:"bg-green-600 text-white",
};

function HcpNode({h,d,s,onS}:{h:H,d:number,s:string|null,onS:(x:H)=>void}) {
  const [open,setOpen]=useState(d===0);
  const kids=h.children||[];
  const ini=h.name.split(" ").map((w:string)=>w[0]).join("").slice(0,2);
  return (
    <div>
      <div className="flex">
        {d>0&&<div style={{width:`${d*18}px`}} className="flex-shrink-0 flex items-center pr-1 mt-5">
          <div className="flex-1 h-px bg-gray-700"/>
        </div>}
        <motion.button
          whileHover={{scale:1.01}} whileTap={{scale:0.97}}
          onClick={()=>{onS(h);if(kids.length)setOpen(o=>!o);}}
          className={`flex-1 flex items-center gap-2.5 px-3 py-2.5 rounded-xl border text-left my-0.5 transition-all ${
            s===h.id?"bg-blue-500/20 border-blue-400/50":"bg-gray-800/80 border-gray-700 hover:border-gray-500"}`}>
          <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0 ${TS[h.kol_tier||"local"]||"bg-gray-600 text-white"}`}>
            {ini}
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-white text-sm font-medium truncate">{h.name}</div>
            {h.specialty&&<div className="text-gray-400 text-[11px] truncate">{h.specialty}</div>}
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            {h.kol_tier&&<span className={`text-[10px] px-2 py-0.5 rounded-full border ${BD[h.kol_tier]||BD.local}`}>{h.kol_tier}</span>}
            {h.influence_score!=null&&<span className="text-xs text-gray-400 font-mono">{h.influence_score.toFixed(1)}</span>}
            {kids.length>0&&<motion.span animate={{rotate:open?0:-90}} className="text-gray-500 text-xs">&#9662;</motion.span>}
          </div>
        </motion.button>
      </div>
      <AnimatePresence>
        {open&&kids.length>0&&(
          <motion.div initial={{height:0,opacity:0}} animate={{height:"auto",opacity:1}} exit={{height:0,opacity:0}} transition={{duration:0.2}} className="overflow-hidden">
            <div className="border-l border-gray-700 ml-4 pl-1">
              {kids.map(c=><HcpNode key={c.id} h={c} d={d+1} s={s} onS={onS}/>)}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function DetailPanel({h,close}:{h:H,close:()=>void}) {
  return (
    <motion.div
      initial={{x:20,opacity:0}} animate={{x:0,opacity:1}} exit={{x:20,opacity:0}}
      transition={{type:"spring",stiffness:280,damping:28}}
      className="w-64 flex-shrink-0 bg-gray-900 border border-gray-700 rounded-2xl p-5 space-y-4 sticky top-4">
      <div className="flex justify-between items-start">
        <div>
          <p className="text-white font-bold">{h.name}</p>
          {h.specialty&&<p className="text-gray-400 text-sm mt-0.5">{h.specialty}</p>}
        </div>
        <button onClick={close} className="text-gray-500 hover:text-white text-xl leading-none">&times;</button>
      </div>
      <div className="space-y-2.5 text-sm">
        {h.kol_tier&&(
          <div className="flex justify-between items-center">
            <span className="text-gray-400">Tier</span>
            <span className={`text-[10px] px-2 py-0.5 rounded-full border ${BD[h.kol_tier]||BD.local}`}>{h.kol_tier}</span>
          </div>
        )}
        {h.influence_score!=null&&(
          <div className="flex justify-between">
            <span className="text-gray-400">Influence Score</span>
            <span className="text-white font-mono">{h.influence_score.toFixed(1)}</span>
          </div>
        )}
        {h.institution&&(
          <div className="flex justify-between gap-2">
            <span className="text-gray-400 flex-shrink-0">Institution</span>
            <span className="text-white text-right text-xs truncate">{h.institution}</span>
          </div>
        )}
        {(h.children||[]).length>0&&(
          <div className="flex justify-between">
            <span className="text-gray-400">Direct Connections</span>
            <span className="text-white">{h.children!.length}</span>
          </div>
        )}
      </div>
      <div className="pt-1 space-y-2">
        <a href={`/hcps/${h.id}`} className="block text-center bg-blue-600 hover:bg-blue-500 text-white text-xs py-2 rounded-lg transition-colors">
          View Full Profile
        </a>
        <a href={`/nba?hcp=${h.id}`} className="block text-center bg-gray-700 hover:bg-gray-600 text-white text-xs py-2 rounded-lg transition-colors">
          Next Best Actions
        </a>
      </div>
    </motion.div>
  );
}

export default function GraphPage() {
  const [hcps,setHcps]=useState<H[]>([]);
  const [sel,setSel]=useState<H|null>(null);
  const [q,setQ]=useState("");
  const [tier,setTier]=useState("all");
  const [loading,setLoading]=useState(true);
  const [stats,setStats]=useState({total:0,national:0,regional:0,local:0});

  useEffect(()=>{
    fetch(`${API}/hcps?limit=120`)
      .then(r=>r.json())
      .then((d:any)=>{
        const all:H[]=(d.items||d||[]).map((h:any)=>({
          id:h.id,name:h.name,specialty:h.specialty,
          kol_tier:h.kol_tier,influence_score:h.influence_score,
          institution:h.institution_name||h.institution,
        }));
        const nat=all.filter(h=>h.kol_tier==="national");
        const reg=all.filter(h=>h.kol_tier==="regional");
        const rest=all.filter(h=>h.kol_tier!=="national"&&h.kol_tier!=="regional");
        nat.forEach((n,i)=>{
          const myR=reg.filter((_:any,j:number)=>j%Math.max(nat.length,1)===i).slice(0,4);
          n.children=myR.map((rv:any)=>({
            ...rv,
            children:rest.filter((_:any,k:number)=>k%Math.max(reg.length,1)===reg.indexOf(rv)).slice(0,3),
          }));
        });
        setStats({total:all.length,national:nat.length,regional:reg.length,local:rest.length});
        setHcps(nat.length>0?nat:all.slice(0,25));
      })
      .catch(()=>setHcps([]))
      .finally(()=>setLoading(false));
  },[]);

  const show=hcps.filter(h=>
    (tier==="all"||h.kol_tier===tier)&&
    (!q||h.name.toLowerCase().includes(q.toLowerCase()))
  );

  return (
    <div className="min-h-screen bg-gray-950 p-6">
      <div className="max-w-6xl mx-auto">
        <motion.div initial={{opacity:0,y:-14}} animate={{opacity:1,y:0}} className="mb-6">
          <h1 className="text-2xl font-bold text-white">Knowledge Graph</h1>
          <p className="text-gray-400 text-sm mt-1">HCP hierarchy by KOL tier. Click any lead to expand connections and view profile.</p>
        </motion.div>

        {/* Stats */}
        <div className="grid grid-cols-4 gap-3 mb-5">
          {[
            {label:"Total HCPs",value:stats.total,color:"text-white"},
            {label:"National KOLs",value:stats.national,color:"text-yellow-400"},
            {label:"Regional KOLs",value:stats.regional,color:"text-blue-400"},
            {label:"Local / Emerging",value:stats.local,color:"text-gray-400"},
          ].map(s=>(
            <motion.div key={s.label} initial={{opacity:0,y:8}} animate={{opacity:1,y:0}}
              className="bg-gray-900 border border-gray-700 rounded-xl px-4 py-3">
              <div className={`text-xl font-bold ${s.color}`}>{s.value}</div>
              <div className="text-xs text-gray-500 mt-0.5">{s.label}</div>
            </motion.div>
          ))}
        </div>

        {/* Filters */}
        <div className="flex flex-wrap gap-3 mb-5">
          <input value={q} onChange={e=>setQ(e.target.value)} placeholder="Search HCPs..."
            className="bg-gray-800 border border-gray-700 rounded-xl px-4 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-blue-500 w-52"/>
          {["all","national","regional","local","emerging"].map(t=>(
            <button key={t} onClick={()=>setTier(t)}
              className={`px-3 py-2 rounded-xl text-xs font-medium transition-colors ${
                tier===t?"bg-blue-600 text-white":"bg-gray-800 text-gray-400 hover:text-white border border-gray-700"}`}>
              {t[0].toUpperCase()+t.slice(1)}
            </button>
          ))}
        </div>

        {/* Tree + Panel */}
        <div className="flex gap-5 items-start">
          <motion.div layout className="flex-1 min-w-0 space-y-0.5">
            {loading&&[...Array(6)].map((_,i)=>(
              <motion.div key={i} initial={{opacity:0}} animate={{opacity:1}} transition={{delay:i*0.07}}
                className="h-14 bg-gray-800 rounded-xl animate-pulse mb-2"/>
            ))}
            {!loading&&show.length===0&&(
              <div className="text-center text-gray-500 py-20">No HCPs match current filters</div>
            )}
            {!loading&&show.map((h,i)=>(
              <motion.div key={h.id} initial={{opacity:0,y:6}} animate={{opacity:1,y:0}} transition={{delay:i*0.03}}>
                <HcpNode h={h} d={0} s={sel?.id||null} onS={setSel}/>
              </motion.div>
            ))}
          </motion.div>
          <AnimatePresence>
            {sel&&<DetailPanel key={sel.id} h={sel} close={()=>setSel(null)}/>}
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}

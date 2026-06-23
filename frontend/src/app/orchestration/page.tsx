"use client";
import {useState} from "react";
import {motion,AnimatePresence} from "motion/react";
const S=[
  {id:"ingestion",label:"Ingestion",icon:"⬇",color:"from-violet-500 to-purple-600",border:"border-violet-400",desc:"20 research API connectors",agents:[
    {id:"pubmed",name:"PubMed",iv:"1h",cfg:{query:"oncology",max_results:500}},
    {id:"ct",name:"ClinicalTrials.gov",iv:"2h",cfg:{condition:"cancer",status:"RECRUITING"}},
    {id:"ss",name:"Semantic Scholar",iv:"6h",cfg:{min_citation_count:5}},
    {id:"oa",name:"OpenAlex",iv:"6h",cfg:{concept:"C71924100"}},
    {id:"fda",name:"FDA openFDA",iv:"12h",cfg:{application_type:"NDA,BLA"}},
    {id:"biorxiv",name:"bioRxiv/medRxiv",iv:"4h",cfg:{keywords:"oncology,tumor"}},
    {id:"clinvar",name:"ClinVar",iv:"24h",cfg:{genes:"BRCA1,BRCA2,KRAS,EGFR"}},
    {id:"twitter",name:"Twitter Monitor",iv:"2h",cfg:{hashtags:"#ASCO #oncology"}},
    {id:"nccn",name:"NCCN Watcher",iv:"48h",cfg:{hash_check:true}},
    {id:"asco",name:"ASCO Scraper",iv:"24h",cfg:{selector:".abstract-card"}},
  ]},
  {id:"identity",label:"Identity Resolution",icon:"🔗",color:"from-blue-500 to-cyan-600",border:"border-blue-400",desc:"NPI + email + fuzzy name dedup",agents:[
    {id:"resolver",name:"HCP Resolver",iv:"on-ingest",cfg:{fuzzy_threshold:88}},
    {id:"apollo",name:"Apollo Enrichment",iv:"on-resolve",cfg:{fields:"linkedin_url,twitter_handle,email"}},
  ]},
  {id:"graph",label:"Knowledge Graph",icon:"🕸",color:"from-emerald-500 to-teal-600",border:"border-emerald-400",desc:"Neo4j: HCP, Publication, Trial nodes",agents:[
    {id:"gb",name:"Graph Builder",iv:"on-resolve",cfg:{edges:"AUTHORED,INVESTIGATES,CO_AUTHOR,CO_INVESTIGATOR"}},
    {id:"ra",name:"Referral Analyzer",iv:"6h",cfg:{min_shared_pubs:2}},
  ]},
  {id:"enrichment",label:"Enrichment",icon:"✨",color:"from-amber-500 to-orange-600",border:"border-amber-400",desc:"Claude Sonnet + Voyage AI embeddings",agents:[
    {id:"pe",name:"Publication Enrichment",iv:"on-ingest",cfg:{model:"claude-sonnet-4-6",extract:"disease_areas,biomarkers,therapies"}},
    {id:"emb",name:"Voyage Embeddings",iv:"on-enrich",cfg:{model:"voyage-3",dimensions:1024}},
    {id:"hp",name:"HCP Profile Enricher",iv:"24h",cfg:{sources:"apollo,semantic_scholar,openalex"}},
  ]},
  {id:"scoring",label:"Scoring & Classification",icon:"📊",color:"from-pink-500 to-rose-600",border:"border-pink-400",desc:"KOL score, tiers, territory, competitor affinity",agents:[
    {id:"kol",name:"KOL Scorer",iv:"6h",cfg:{publication_count:0.20,trial_participation:0.20,citations:0.20,h_index:0.15,recent_pubs:0.15,trigger_events:0.10}},
    {id:"clf",name:"KOL Classifier",iv:"6h",cfg:{national:80,regional:60,local:40}},
    {id:"terr",name:"Territory Engine",iv:"12h",cfg:{hcp_density:0.30,kol_presence:0.25,trial_volume:0.25,trigger_momentum:0.20}},
    {id:"ca",name:"Competitor Affinity",iv:"12h",cfg:{trial_weight:2,pub_weight:1}},
  ]},
  {id:"intelligence",label:"Intelligence Agents",icon:"🧠",color:"from-indigo-500 to-blue-700",border:"border-indigo-400",desc:"Deep analysis via Claude Sonnet & Haiku",agents:[
    {id:"ri",name:"Research Intelligence",iv:"24h",cfg:{model:"claude-sonnet-4-6",sources:"pubmed,ss,openalex,biorxiv"}},
    {id:"pi",name:"Publication Intelligence",iv:"24h",cfg:{metrics:"citation_network,journal_velocity,whitespace"}},
    {id:"ti",name:"Trial Intelligence",iv:"12h",cfg:{model:"claude-haiku-4-5-20251001",phases:"I,II,III,IV"}},
    {id:"ci",name:"Competitor Intelligence",iv:"24h",cfg:{signals:"fda_approvals,news,hcp_affinity,trial_volume"}},
  ]},
  {id:"triggers",label:"Trigger Detection",icon:"⚡",color:"from-yellow-500 to-amber-600",border:"border-yellow-400",desc:"All 8 trigger types + NBA engine",agents:[
    {id:"td",name:"Trigger Detector",iv:"1h",cfg:{types:"new_publication,trial_enrollment_opened,conference_presentation,institution_change,grant_awarded,advisory_board_appointment,competitor_drug_approved,guideline_update"}},
    {id:"nba",name:"NBA Engine",iv:"on-trigger",cfg:{model:"claude-haiku-4-5-20251001",actions:"send_linkedin,send_email,schedule_call,invite_to_advisory,trial_referral,share_data"}},
  ]},
  {id:"messaging",label:"Messaging & Compliance",icon:"📨",color:"from-teal-500 to-green-600",border:"border-teal-400",desc:"Evidence-backed messages + audit trail",agents:[
    {id:"mg",name:"Message Generator",iv:"on-nba",cfg:{model:"claude-sonnet-4-6",validation:"wiley_tdm"}},
    {id:"gv",name:"Grammar Validator",iv:"on-generate",cfg:{primary:"wiley_tdm",fallback:"claude-haiku-4-5-20251001"}},
    {id:"cv",name:"Citation Verifier",iv:"on-generate",cfg:{strategy:"doi,nct,fuzzy_title",min_compliance_score:0.8}},
    {id:"am",name:"Compliance Audit",iv:"always",cfg:{table:"compliance_audit_log",skip:["/health","/docs"]}},
  ]},
];
type St=typeof S[number];type Ag=St["agents"][number];
function Cfg({ag,st,close}:{ag:Ag,st:St,close:()=>void}) {
  const [v,setV]=useState(()=>JSON.stringify(ag.cfg,null,2));
  const [ok,setOk]=useState(false);
  return (
    <motion.div initial={{opacity:0}} animate={{opacity:1}} exit={{opacity:0}} className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm" onClick={close}>
      <motion.div initial={{scale:0.9,y:20}} animate={{scale:1,y:0}} exit={{scale:0.9,y:20}} transition={{type:"spring",stiffness:320,damping:28}}
        className="bg-gray-900 border border-gray-700 rounded-2xl shadow-2xl w-full max-w-lg mx-4 overflow-hidden" onClick={e=>e.stopPropagation()}>
        <div className={`bg-gradient-to-r ${st.color} px-6 py-4 flex items-center justify-between`}>
          <div><p className="text-xs text-white/60 uppercase tracking-wider">{st.label}</p><h2 className="text-white font-bold text-lg">{ag.name}</h2></div>
          <div className="flex items-center gap-3">
            <span className="bg-white/20 text-white text-xs px-2 py-1 rounded-full flex items-center gap-1.5"><span className="w-1.5 h-1.5 rounded-full bg-green-300 animate-pulse"/>{ag.iv}</span>
            <button onClick={close} className="text-white/70 hover:text-white text-xl leading-none">&times;</button>
          </div>
        </div>
        <div className="p-6 space-y-4">
          <label className="text-xs text-gray-400 uppercase tracking-wider block">Configuration (JSON)</label>
          <textarea className="w-full bg-gray-800 border border-gray-700 rounded-xl text-sm text-green-300 font-mono p-3 h-48 resize-none focus:outline-none focus:border-blue-500" value={v} onChange={e=>setV(e.target.value)}/>
          <div className="flex gap-3">
            <motion.button whileTap={{scale:0.95}} onClick={()=>{setOk(true);setTimeout(()=>setOk(false),2000);}}
              className={`flex-1 py-2.5 rounded-xl font-medium text-sm text-white transition-colors ${ok?"bg-green-600":"bg-blue-600 hover:bg-blue-500"}`}>
              {ok?"✓ Saved":"Save Configuration"}
            </motion.button>
            <motion.button whileTap={{scale:0.95}} onClick={close} className="px-4 py-2.5 rounded-xl border border-gray-600 text-gray-300 hover:border-gray-400 text-sm">Cancel</motion.button>
          </div>
        </div>
      </motion.div>
    </motion.div>
  );
}
function Ab({ag,st,i}:{ag:Ag,st:St,i:number}) {
  const [open,setOpen]=useState(false);
  return (
    <>
      <motion.button initial={{opacity:0,y:8}} animate={{opacity:1,y:0}} transition={{delay:i*0.05}} whileHover={{scale:1.04,y:-2}} whileTap={{scale:0.96}} onClick={()=>setOpen(true)}
        className={`relative bg-gray-800 border ${st.border} border-opacity-30 hover:border-opacity-100 rounded-xl px-3 py-2.5 text-left group cursor-pointer transition-all`}>
        <div className="flex items-center justify-between gap-2">
          <span className="text-white text-xs font-medium truncate">{ag.name}</span>
          <span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse flex-shrink-0"/>
        </div>
        <div className="text-gray-500 text-[10px] mt-0.5">{ag.iv}</div>
        <div className="absolute inset-0 rounded-xl bg-white/0 group-hover:bg-white/5 transition-colors pointer-events-none"/>
      </motion.button>
      <AnimatePresence>{open&&<Cfg ag={ag} st={st} close={()=>setOpen(false)}/>}</AnimatePresence>
    </>
  );
}
function Card({st,si}:{st:St,si:number}) {
  const [col,setCol]=useState(false);
  return (
    <motion.div initial={{opacity:0,x:-16}} animate={{opacity:1,x:0}} transition={{delay:si*0.06,type:"spring",stiffness:200,damping:22}} className="relative">
      {si<S.length-1&&<div className="absolute left-1/2 -bottom-6 -translate-x-1/2 flex flex-col items-center z-10 pointer-events-none"><div className="w-px h-4 bg-gray-600"/><span className="text-gray-600 text-xs">▼</span></div>}
      <div className="bg-gray-900 border border-gray-700 rounded-2xl overflow-hidden">
        <motion.button whileHover={{backgroundColor:"rgba(255,255,255,0.03)"}} onClick={()=>setCol(c=>!c)}
          className={`w-full flex items-center gap-3 px-4 py-3.5 bg-gradient-to-r ${st.color} text-left`}>
          <span className="text-2xl">{st.icon}</span>
          <div className="flex-1 min-w-0">
            <div className="text-white font-semibold text-sm"><span className="text-white/40 mr-2">Stage {si+1}</span>{st.label}</div>
            <div className="text-white/60 text-xs">{st.desc}</div>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs text-white/50 bg-white/10 px-2 py-0.5 rounded-full">{st.agents.length} agents</span>
            <motion.span animate={{rotate:col?-90:0}} className="text-white/50 text-sm">▾</motion.span>
          </div>
        </motion.button>
        <AnimatePresence initial={false}>
          {!col&&(
            <motion.div initial={{height:0,opacity:0}} animate={{height:"auto",opacity:1}} exit={{height:0,opacity:0}} transition={{duration:0.22}} className="overflow-hidden">
              <div className="p-3 grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-2">
                {st.agents.map((a,i)=><Ab key={a.id} ag={a} st={st} i={i}/>)}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </motion.div>
  );
}
export default function OrchestrationPage() {
  const total=S.reduce((n,s)=>n+s.agents.length,0);
  return (
    <div className="min-h-screen bg-gray-950 p-6">
      <div className="max-w-5xl mx-auto space-y-7">
        <motion.div initial={{opacity:0,y:-14}} animate={{opacity:1,y:0}} className="flex items-start justify-between">
          <div><h1 className="text-2xl font-bold text-white">Agent Orchestration</h1><p className="text-gray-400 text-sm mt-1">Click any agent block to configure. Pipeline flows top to bottom.</p></div>
          <div className="flex gap-3">
            <div className="bg-gray-800 border border-gray-700 rounded-xl px-4 py-2 text-center"><div className="text-xl font-bold text-white">{S.length}</div><div className="text-xs text-gray-400">Stages</div></div>
            <div className="bg-gray-800 border border-gray-700 rounded-xl px-4 py-2 text-center"><div className="text-xl font-bold text-green-400">{total}</div><div className="text-xs text-gray-400">Agents</div></div>
          </div>
        </motion.div>
        <div className="space-y-7">{S.map((s,i)=><Card key={s.id} st={s} si={i}/>)}</div>
      </div>
    </div>
  );
}

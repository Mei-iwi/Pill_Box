import * as THREE from './vendor/three.module.min.js';
const host=document.getElementById('pillbox-3d');
try { if(host) mount(host); } catch(error) {console.error(error);document.getElementById('model-fallback').hidden=false;}
function mount(host) {
  const reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
  const renderer=new THREE.WebGLRenderer({alpha:true,antialias:true,powerPreference:'low-power'});
  renderer.setPixelRatio(Math.min(devicePixelRatio,2));renderer.shadowMap.enabled=true;renderer.shadowMap.type=THREE.PCFSoftShadowMap;renderer.outputColorSpace=THREE.SRGBColorSpace;host.append(renderer.domElement);
  const scene=new THREE.Scene(),camera=new THREE.PerspectiveCamera(34,1,.1,60);
  scene.add(new THREE.HemisphereLight(0xffffff,0x849085,2.3));
  const light=new THREE.DirectionalLight(0xfff6e7,3.2);light.position.set(-3,7,5);light.castShadow=true;light.shadow.mapSize.set(1024,1024);light.shadow.camera.left=-6;light.shadow.camera.right=6;light.shadow.camera.top=6;light.shadow.camera.bottom=-6;light.shadow.bias=-.0003;scene.add(light);
  const fill=new THREE.DirectionalLight(0xc5e1d8,1.2);fill.position.set(4,4,-4);scene.add(fill);
  const material=(color,roughness=.4,metalness=.08)=>new THREE.MeshStandardMaterial({color,roughness,metalness});
  const porcelain=material(0xe9ede5,.3),forest=material(0x254d40),metal=material(0x9ba99e,.27,.6),lining=material(0xc6d4c6,.7),rubber=material(0x304039,.9);
  function box(w,h,d,mat,x,y,z,parent=scene,r=.055) {
    r=Math.min(r,w/5,h/5,d/5);const s=new THREE.Shape();s.moveTo(-w/2+r,-h/2);s.lineTo(w/2-r,-h/2);s.quadraticCurveTo(w/2,-h/2,w/2,-h/2+r);s.lineTo(w/2,h/2-r);s.quadraticCurveTo(w/2,h/2,w/2-r,h/2);s.lineTo(-w/2+r,h/2);s.quadraticCurveTo(-w/2,h/2,-w/2,h/2-r);s.lineTo(-w/2,-h/2+r);s.quadraticCurveTo(-w/2,-h/2,-w/2+r,-h/2);
    const g=new THREE.ExtrudeGeometry(s,{depth:d-r*2,bevelEnabled:true,bevelSize:r,bevelThickness:r,bevelSegments:4,steps:1,curveSegments:6});g.center();const mesh=new THREE.Mesh(g,mat);mesh.position.set(x,y,z);mesh.castShadow=true;mesh.receiveShadow=true;parent.add(mesh);return mesh;
  }
  function textTexture(text,color='#ddf0e1') {const canvas=document.createElement('canvas');canvas.width=512;canvas.height=128;const c=canvas.getContext('2d');c.fillStyle=color;c.textAlign='center';c.font='600 50px sans-serif';c.fillText(text,256,84);const texture=new THREE.CanvasTexture(canvas);texture.colorSpace=THREE.SRGBColorSpace;return texture;}
  function label(text,w,h,x,y,z,parent=scene,flat=false,color) {const mesh=new THREE.Mesh(new THREE.PlaneGeometry(w,h),new THREE.MeshBasicMaterial({map:textTexture(text,color),transparent:true,depthWrite:false}));mesh.position.set(x,y,z);if(flat)mesh.rotation.x=-Math.PI/2;parent.add(mesh);return mesh;}
  const ground=new THREE.Mesh(new THREE.PlaneGeometry(60,60),new THREE.ShadowMaterial({color:0x3e5949,opacity:.19}));ground.rotation.x=-Math.PI/2;ground.position.y=-.02;ground.receiveShadow=true;scene.add(ground);
  box(3.95,.19,2.7,forest,0,.13,0);box(3.94,.22,2.7,porcelain,0,1.06,0);
  box(.14,.80,2.63,porcelain,-1.89,.61,0);box(.14,.80,2.63,porcelain,1.89,.61,0);box(3.76,.78,.13,porcelain,0,.61,-1.25);
  for(const x of [-.63,.63])box(.09,.70,2.30,porcelain,x,.57,-.05);
  for(const x of [-1.55,1.55])for(const z of [-.93,.93])box(.25,.08,.25,rubber,x,.025,z);
  box(3.4,.024,2.14,forest,0,1.24,-.04);label('PILLBOX',.85,.21,-1.12,1.266,-.74,scene,true);
  const lcd=document.createElement('canvas');lcd.width=640;lcd.height=300;const lcdTexture=new THREE.CanvasTexture(lcd);lcdTexture.colorSpace=THREE.SRGBColorSpace;
  box(1.78,.045,.89,rubber,-.64,1.28,.03);const screen=new THREE.Mesh(new THREE.PlaneGeometry(1.64,.77),new THREE.MeshBasicMaterial({map:lcdTexture}));screen.rotation.x=-Math.PI/2;screen.position.set(-.64,1.32,.03);scene.add(screen);
  const targets=[],lamps=[];
  for(const [i,action] of ['scan','refill','silence'].entries()){
    const z=-.62+i*.57,button=new THREE.Mesh(new THREE.CylinderGeometry(.15,.17,.07,32),material(i===1?0xc8dfc9:0x607f6a));button.position.set(.63,1.31,z);button.castShadow=true;button.userData.action=action;scene.add(button);targets.push(button);label(['SCAN','ADD','MUTE'][i],.49,.13,1.22,1.266,z,scene,true);
  }
  const scanWindow=box(.66,.025,.15,material(0x102520,.12),-.65,1.28,.72);scanWindow.userData.action='scan';targets.push(scanWindow);label('BARCODE',.65,.11,-.65,1.266,.94,scene,true);
  const beam=box(.58,.007,.012,new THREE.MeshBasicMaterial({color:0xea7259}),-.65,1.31,.72);beam.visible=false;
  const packageGroup=new THREE.Group();scene.add(packageGroup);packageGroup.visible=false;box(.72,.88,.23,material(0xf4ecdb),0,0,0,packageGroup);label('THUỐC',.62,.15,0,.20,.125,packageGroup,false,'#2b5944');
  const barcodeCanvas=document.createElement('canvas');barcodeCanvas.width=256;barcodeCanvas.height=100;const bc=barcodeCanvas.getContext('2d');bc.fillStyle='#fff';bc.fillRect(0,0,256,100);bc.fillStyle='#183b2a';for(let i=12;i<244;i+=7)bc.fillRect(i,5,i%3+1,85);const barcodeTexture=new THREE.CanvasTexture(barcodeCanvas);const barcodeMesh=new THREE.Mesh(new THREE.PlaneGeometry(.58,.28),new THREE.MeshBasicMaterial({map:barcodeTexture}));barcodeMesh.position.set(0,-.10,.13);packageGroup.add(barcodeMesh);
  const drawers=[],counts=[0,0,0];
  for(let i=0;i<3;i++){
    const x=(i-1)*1.26,group=new THREE.Group();group.position.x=x;scene.add(group);box(1.12,.08,2.2,lining,0,.29,.02,group);
    for(const side of [-1,1]){box(.065,.37,2.18,lining,side*.55,.48,.02,group);box(.022,.045,1.94,metal,x+side*.595,.39,-.04);}
    box(1.12,.37,.06,lining,0,.48,-1.05,group);const face=box(1.19,.62,.18,porcelain,0,.55,1.20,group);face.userData.slot=i+1;targets.push(face);
    const handle=box(.62,.10,.14,forest,0,.57,1.36,group);handle.userData.slot=i+1;targets.push(handle);label('0'+(i+1),.23,.10,0,.76,1.301,group,false,'#315944');
    const lamp=new THREE.Mesh(new THREE.SphereGeometry(.025,16,10),new THREE.MeshBasicMaterial({color:0x79a38a}));lamp.position.set(.44,.76,1.303);group.add(lamp);lamps.push(lamp);
    const pills=[];for(let j=0;j<12;j++){const geometry=j%3===0?new THREE.CapsuleGeometry(.07,.13,5,12):j%3===1?new THREE.CylinderGeometry(.09,.09,.06,20):new THREE.SphereGeometry(.085,16,12);const pill=new THREE.Mesh(geometry,material([0xe6af88,0xf4e8bf,0xb8d7bf][j%3]));if(j%3===0)pill.rotation.z=Math.PI/2;if(j%3===2)pill.scale.set(1.5,.5,1);pill.position.set((j%3-1)*.25,.39,.25+Math.floor(j/3)*.13);pill.rotation.y=j*.67;pill.visible=false;pill.castShadow=true;group.add(pill);pills.push(pill);}
    drawers.push({group,open:false,target:0,pills});
  }
  let selected=1,data=null,scenario='idle',barcodeResult='',yaw=.48,pitch=.63,distance=7.4,raf=0,visible=true,drag=null,moved=false,scanStart=0;
  const ray=new THREE.Raycaster(),mouse=new THREE.Vector2(),target=new THREE.Vector3(0,.55,.25);
  function drawScreen(){
    const c=lcd.getContext('2d');c.fillStyle='#0b211a';c.fillRect(0,0,640,300);c.fillStyle='#15372b';for(let y=2;y<300;y+=5)c.fillRect(0,y,640,1);
    c.fillStyle='#b9ecc9';c.font='600 68px monospace';c.fillText(new Intl.DateTimeFormat('vi-VN',{timeZone:'Asia/Ho_Chi_Minh',hour:'2-digit',minute:'2-digit',second:'2-digit',hourCycle:'h23'}).format(new Date()),32,86);
    const slot=data?.slots?.find(s=>s.slot_id===selected);c.font='600 31px sans-serif';c.fillStyle='#e5ffeb';c.fillText(('0'+selected+' / '+(slot?.medication_name||'Chưa gán thuốc')).slice(0,30),32,144);
    c.font='26px sans-serif';c.fillStyle='#96bfa4';c.fillText(barcodeResult||({idle:'Mô phỏng • '+counts[selected-1]+' viên',remind:'Đến giờ lấy thuốc',alert:'Cảnh báo • Kiểm tra ngăn',muted:'Đã tắt báo mô phỏng'}[scenario]),32,196);c.font='24px sans-serif';c.fillText(drawers[selected-1].open?'NGĂN KÉO ĐANG MỞ':'BẤM NGĂN ĐỂ MỞ',32,252);lcdTexture.needsUpdate=true;
    lamps.forEach((l,i)=>l.material.color.set(i===selected-1&&scenario==='alert'?0xed634b:i===selected-1&&scenario==='remind'?0xefbd54:0x79a38a));
  }
  function request(){if(!raf&&visible)raf=requestAnimationFrame(animate);}
  function animate(){raf=0;let moving=false;for(const drawer of drawers){const delta=drawer.target-drawer.group.position.z;if(Math.abs(delta)>.002){drawer.group.position.z+=delta*(reduced?1:.17);moving=true;}}
    if(scanStart){const progress=Math.min(1,(performance.now()-scanStart)/1100);packageGroup.visible=true;beam.visible=true;packageGroup.position.set(-.64,2.2-progress*.65,.72);packageGroup.rotation.x=-.6;moving=true;if(progress>=1){scanStart=0;packageGroup.visible=false;beam.visible=false;}}
    const w=host.clientWidth,h=host.clientHeight;if(w&&h){renderer.setSize(w,h,false);camera.aspect=w/h;const d=distance*Math.max(1,1.42/camera.aspect)+(drawers.some(x=>x.open)?.7:0);camera.position.set(Math.sin(yaw)*Math.cos(pitch)*d,.55+Math.sin(pitch)*d,Math.cos(yaw)*Math.cos(pitch)*d);camera.lookAt(target);camera.updateProjectionMatrix();renderer.render(scene,camera);}if(moving)request();
  }
  function select(slot){selected=Math.max(1,Math.min(3,Number(slot)||1));drawScreen();request();host.dispatchEvent(new CustomEvent('pillbox:select',{detail:{slot:selected}}));}
  function toggleLid(slot=selected){const drawer=drawers[slot-1];drawer.open=!drawer.open;drawer.target=drawer.open?1.5:0;drawScreen();request();return drawer.open;}
  const events=new AbortController();
  host.addEventListener('pointerdown',e=>{drag={x:e.clientX,y:e.clientY,yaw,pitch};moved=false;host.setPointerCapture(e.pointerId);},{signal:events.signal});
  host.addEventListener('pointermove',e=>{if(!drag)return;const dx=e.clientX-drag.x,dy=e.clientY-drag.y;if(Math.abs(dx)+Math.abs(dy)>6)moved=true;yaw=drag.yaw-dx*.006;pitch=Math.min(1.3,Math.max(.15,drag.pitch+dy*.005));request();},{signal:events.signal});
  host.addEventListener('pointerup',e=>{if(drag&&!moved){const r=renderer.domElement.getBoundingClientRect();mouse.set((e.clientX-r.left)/r.width*2-1,1-(e.clientY-r.top)/r.height*2);ray.setFromCamera(mouse,camera);const hit=ray.intersectObjects(targets)[0]?.object;if(hit?.userData.slot){select(hit.userData.slot);toggleLid(selected);host.dispatchEvent(new CustomEvent('pillbox:lid',{detail:{slot:selected,open:drawers[selected-1].open}}));}if(hit?.userData.action){hit.position.y-=.025;request();setTimeout(()=>{hit.position.y+=.025;request();},120);host.dispatchEvent(new CustomEvent('pillbox:action',{detail:{action:hit.userData.action}}));}}drag=null;},{signal:events.signal});
  host.addEventListener('pointercancel',()=>{drag=null;},{signal:events.signal});host.addEventListener('wheel',e=>{e.preventDefault();distance=Math.min(12,Math.max(5.7,distance+Math.sign(e.deltaY)*.35));request();},{passive:false,signal:events.signal});
  const resize=new ResizeObserver(request);resize.observe(host);const observer=new IntersectionObserver(entries=>{visible=entries[0].isIntersecting;if(visible)request();});observer.observe(host);const timer=setInterval(()=>{if(document.visibilityState==='visible'){drawScreen();request();}},1000);
  window.pillboxModel={select,toggleLid,reset(){yaw=.48;pitch=.63;distance=7.4;request();},update(snapshot){data=snapshot;drawScreen();request();},isLidOpen(slot){return drawers[slot-1].open;},isScanning(){return Boolean(scanStart);},closeAll(){drawers.forEach(d=>{d.open=false;d.target=0;});drawScreen();request();},setBarcodeResult(value){barcodeResult=value;drawScreen();request();},scanPackage(){scanStart=performance.now();request();},setScenario(value){scenario=value;barcodeResult='';drawScreen();request();},addPills(slot,amount){counts[slot-1]=Math.min(12,counts[slot-1]+amount);drawers[slot-1].pills.forEach((p,i)=>p.visible=i<counts[slot-1]);drawScreen();request();return counts[slot-1];},resetSimulation(){counts.fill(0);drawers.forEach(d=>d.pills.forEach(p=>p.visible=false));scenario='idle';barcodeResult='';this.closeAll();},destroy(){clearInterval(timer);cancelAnimationFrame(raf);events.abort();resize.disconnect();observer.disconnect();scene.traverse(o=>{o.geometry?.dispose();const mats=Array.isArray(o.material)?o.material:[o.material];mats.filter(Boolean).forEach(m=>{m.map?.dispose();m.dispose();});});renderer.dispose();renderer.domElement.remove();}};
  window.dispatchEvent(new Event('pillbox:model-ready'));drawScreen();request();
}

// Logic nghiệp vụ thuần cho prototype; trạng thái rà soát tách khỏi trạng thái giao dịch.
(function(root){
 function makeInitial(config,now=Date.now()){
  const customer={...config.customer};
  const transactions=(config.transactions||[{id:'MBL-DEMO-1003',name:'Trần Ngọc Hà',bank:config.banks[1],account:'00712891034',amount:2500000,note:'Minh Anh chuyen tien',direction:'out',time:new Date(now-3600000*3).toISOString()},{id:'MBL-DEMO-1002',name:'Lê Minh Khang',bank:config.banks[2],account:'00712891035',amount:1500000,note:'Hoan tra chi phi',direction:'in',time:new Date(now-3600000*21).toISOString()},{id:'MBL-DEMO-1001',name:'Phạm Thu Trang',bank:config.banks[3],account:'00712891036',amount:4800000,note:'Chi phi sinh hoat',direction:'out',time:new Date(now-3600000*27).toISOString()}]).map(t=>({...t,source:t.source||(t.direction==='in'?t.account:customer.account),account:t.direction==='in'?customer.account:t.account,status:'success',reviewStage:'none',scenario:'normal',fee:0}));
  return {version:1,customer,transactions,notifications:[{id:'MSG-WELCOME',kind:'security',title:'Chủ động bảo vệ tài khoản',text:'Không chia sẻ mật khẩu hoặc mã xác thực với bất kỳ ai. Chỉ xem thông tin hỗ trợ tại kênh chính thức của ngân hàng.',time:new Date(now-3600000*24).toISOString(),read:true,txId:null}],nextSequence:1004,nextScenario:'normal',latestId:null,restriction:false};
 }
 function isRestricted(state){return !!state.restriction||state.transactions.some(t=>t.reviewStage==='protected')}
 function reviewTarget(state){return state.transactions.find(t=>t.reviewStage==='review'&&['protected','cleared'].includes(t.scenario))||state.transactions.find(t=>t.reviewStage==='pending')||state.transactions.find(t=>t.reviewStage==='review')||state.transactions.find(t=>t.id===state.latestId)}
 function validate(form,state,config){const errors={},digits=String(form.account||'').replace(/\s/g,''),amount=Number(form.amount),name=String(form.name||'').trim(),note=String(form.note||'').trim();
  if(!/^\d+$/.test(String(form.bank))||!config.banks[Number(form.bank)])errors.bank='Vui lòng chọn ngân hàng thụ hưởng.';
  if(!/^\d{8,16}$/.test(digits))errors.account='Nhập số tài khoản gồm 8–16 chữ số.';
  else if(digits===state.customer.account.replace(/\s/g,''))errors.account='Vui lòng chọn tài khoản nhận khác tài khoản nguồn.';
  if(!name||name.length<3||name.length>70)errors.name='Nhập tên người nhận từ 3–70 ký tự.';
  if(!Number.isFinite(amount)||!Number.isInteger(amount)||amount<10000)errors.amount='Số tiền tối thiểu là 10.000 VNĐ, không có phần lẻ.';
  else if(amount>200000000)errors.amount='Hạn mức mô phỏng là 200.000.000 VNĐ / giao dịch.';
  else if(amount>state.customer.balance)errors.amount='Số dư minh họa không đủ để thực hiện giao dịch.';
  if(!note||note.length>140)errors.note='Nhập nội dung chuyển tiền, tối đa 140 ký tự.';
  if(isRestricted(state))errors.restriction='Chức năng chuyển tiền đang tạm hạn chế trong kịch bản bảo vệ tài khoản.';
  return errors;
 }
 function addNotification(state,kind,title,text,txId,now){const notification={id:'MSG-'+state.nextSequence+++'-'+kind,kind,title,text,txId,time:new Date(now).toISOString(),read:false};state.notifications.unshift(notification);return notification;}
 function completeTransfer(state,form,config,otp,now=Date.now()){
  if(otp!=='123456')throw new Error('Mã xác thực chưa đúng. Sử dụng mã demo 123456.');
  const errors=validate(form,state,config);if(Object.keys(errors).length)throw new Error(Object.values(errors)[0]);
  const tx={id:'MBL-'+new Date(now).toISOString().slice(0,10).replace(/-/g,'')+'-'+state.nextSequence++,name:form.name.trim(),bank:config.banks[Number(form.bank)],account:form.account.replace(/\s/g,''),source:state.customer.account,amount:Number(form.amount),fee:0,note:form.note.trim(),direction:'out',status:'success',reviewStage:state.nextScenario==='normal'?'none':'pending',scenario:state.nextScenario,time:new Date(now).toISOString()};
  state.customer.balance-=tx.amount;state.transactions.unshift(tx);state.latestId=tx.id;
  addNotification(state,'success','Chuyển tiền thành công','Bạn đã chuyển '+tx.amount.toLocaleString('vi-VN')+' VNĐ đến '+tx.name+'.',tx.id,now);
  return tx;
 }
 function beginReview(state,id,config,now=Date.now()){
  const tx=state.transactions.find(t=>t.id===id);if(!tx||tx.status!=='success'||tx.reviewStage!=='pending')return null;
  tx.reviewStage='review';tx.reviewStarted=new Date(now).toISOString();const message=config.messages.review;return addNotification(state,'review',message.title,message.text,id,now);
 }
 function finishReview(state,id,config,now=Date.now()){
  const tx=state.transactions.find(t=>t.id===id);if(!tx||tx.status!=='success'||tx.reviewStage!=='review'||!['cleared','protected'].includes(tx.scenario))return null;
  tx.reviewStage=tx.scenario;tx.reviewCompleted=new Date(now).toISOString();if(tx.scenario==='protected')state.restriction=true;
  const message=config.messages[tx.scenario];return addNotification(state,tx.scenario,message.title,message.text,id,now);
 }
 root.AEGISMobileModel={makeInitial,isRestricted,reviewTarget,validate,completeTransfer,beginReview,finishReview};
})(typeof window!=='undefined'?window:globalThis);

const execSync = require('child_process').execSync;

// EPGStaion のホストアドレス. 通常ローカル.
const host='localhost:8888';
// エンコードのプリセット名.
const encodePresetName='H.264(rkmpp)';
// 元ファイルを削除するかどうか. true にすると元ファイル(TS)を削除.
const removeOriginalFile=false;
// エンコードキューに投入する最大数.
const maxEnqueueCount=5;


const options='isHalfWidth=true&offset=0&limit=24&hasOriginalFile=false';

function getRecorded()
{
  const result = execSync(`curl --silent -X GET 'http://${host}/api/recorded?${options}' -H 'application/json' | jq '.records'`);
  //console.log(String(result));
  return String(result);
}

function getEncodeList()
{
  json = JSON.parse(getRecorded());
  // 現在エンコード処理中のものがあればまず集合から除外する.
  const isProcessing = function(v) { return !(v.isEncoding || v.isRecording); };
  json = json.filter(isProcessing);

  // エンコード済み状態の集合を作る.
  const hasEncoded = function(v) { return v.type == 'encoded'; };
  const items = json.filter( function(item) { return item.videoFiles.some(hasEncoded); } );

  // まだエンコードされたファイルを持たないものを求める.
  const noEncodedList = json.filter( (v) => !items.includes(v) );
  return noEncodedList;
}

function requestEncode(item)
{
  const videoFiles = item.videoFiles.filter( (v) => v.type == "ts");
  if (videoFiles.length == 0) {
    return;
  }
  const videoFileId = videoFiles[0].id;

  const encOptions = {
    recordedId: item.id,
    sourceVideoFileId: videoFileId,
    removeOriginal: removeOriginalFile,
    isSaveSameDirectory: true,
    mode: encodePresetName,
  };
  const str = JSON.stringify(encOptions);
  console.log(str);
  execSync(`curl --silent -X POST 'http://${host}/api/encode' -d '${str}' -H 'Content-Type: application/json'`);
}

function main()
{
  const list = getEncodeList().reverse();

  for(let i=0; i < Math.min(list.length, maxEnqueueCount); ++i )
  {
    requestEncode(list[i]);
  }
}

main();


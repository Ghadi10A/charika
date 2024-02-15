function startTicker() {
  console.log('startTicker function called');
  var ticker = document.getElementById("news-ticker");
  var list = ticker.getElementsByTagName("ul")[0];
  var listItems = list.getElementsByTagName("li");
  list.style.marginLeft = -listItems[0].offsetWidth + "px";
  
  setInterval(function() {
    list.style.marginLeft = parseInt(list.style.marginLeft) - 1 + "px";
    if (parseInt(list.style.marginLeft) <= -listItems[0].offsetWidth) {
      list.appendChild(listItems[0]);
      list.style.marginLeft = "0px";
    }
  }, 20);
}
$(document).ready(function() {
  startTicker();
});
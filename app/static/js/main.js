document.addEventListener("DOMContentLoaded", () => {
  const ctaButton = document.getElementById("cta-button");

  if (!ctaButton) {
    return;
  }

  ctaButton.addEventListener("click", () => {
    window.alert("기본 랜딩 페이지와 서비스 구조가 준비되었습니다.");
  });
});

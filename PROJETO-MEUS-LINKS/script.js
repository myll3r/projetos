function toggleMode() {
  const html = document.documentElement
  html.classList.toggle("light") // remove a classe do html para ativar o modo dark.//
  // buscando a imagem pelo seletor //
  const img = document.querySelector("#profile img")
  // substituindo a imagem e texto alternativo //
  if (html.classList.contains("light")) {
    img.setAttribute("src", "./assets/avatar-light.png")
    img.setAttribute("alt", "Mulher jovem sorrindo de blusa branca.") //pega a tag img e altera os atributos//
  } else {
    img.setAttribute("src", "./assets/avatar-dark.png")
    img.setAttribute("alt", "Mulher jovem sorrindo de blusa azul.")
  }
}

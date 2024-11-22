document.addEventListener('DOMContentLoaded', () => {
    // Validación del formulario de registro de cultivos
    const registroForm = document.querySelector('#registro-form');
    if (registroForm) {
      registroForm.addEventListener('submit', (e) => {
        const tipoCultivo = document.querySelector('#tipo_cultivo').value.trim();
        const cantidad = document.querySelector('#cantidad').value;
        const ubicacion = document.querySelector('#ubicacion').value.trim();
  
        if (!tipoCultivo || !cantidad || !ubicacion) {
          e.preventDefault();
          alert('Por favor, completa todos los campos antes de enviar.');
        }
      });
    }
  
    // Mostrar alertas dinámicas en la página de alertas
    const alertas = document.querySelectorAll('.alert');
    alertas.forEach((alerta) => {
      alerta.addEventListener('click', () => {
        alerta.classList.add('hidden');
      });
    });
  });
  
  <script>
  document.querySelectorAll('.team-image').forEach(img => {
    img.addEventListener('click', function () {
      const imageSrc = this.getAttribute('data-image');
      document.getElementById('modalImage').src = imageSrc;
    });
  });
</script>

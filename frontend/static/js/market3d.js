
import * as THREE from "three";

const container = document.getElementById("market3d");
const selectedPanel = document.getElementById("selectedProduct");
const addButton = document.getElementById("addButton");
const message = document.getElementById("message");

const scene = new THREE.Scene();
scene.background = new THREE.Color("#b9d9e8");

const camera = new THREE.PerspectiveCamera(
    55,
    container.clientWidth / container.clientHeight,
    0.1,
    1000
);
camera.position.set(10, 9, 14);
camera.lookAt(0, 0, 0);

const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.setSize(container.clientWidth, container.clientHeight);
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
container.appendChild(renderer.domElement);

// Lights
scene.add(new THREE.HemisphereLight(0xffffff, 0x536579, 2));

const sunlight = new THREE.DirectionalLight(0xffffff, 2.5);
sunlight.position.set(7, 14, 8);
sunlight.castShadow = true;
scene.add(sunlight);

// Supermarket floor
const floor = new THREE.Mesh(
    new THREE.PlaneGeometry(28, 24),
    new THREE.MeshStandardMaterial({ color: "#dce3e8", roughness: 0.9 })
);
floor.rotation.x = -Math.PI / 2;
floor.receiveShadow = true;
scene.add(floor);

// Helpers
function makeBox(width, height, depth, color, x, y, z) {
    const mesh = new THREE.Mesh(
        new THREE.BoxGeometry(width, height, depth),
        new THREE.MeshStandardMaterial({ color, roughness: 0.75 })
    );

    mesh.position.set(x, y, z);
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    scene.add(mesh);
    return mesh;
}

function makeText(text, x, y, z) {
    const canvas = document.createElement("canvas");
    canvas.width = 512;
    canvas.height = 128;

    const ctx = canvas.getContext("2d");
    ctx.fillStyle = "#183047";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = "#ffffff";
    ctx.font = "bold 46px Arial";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(String(text).slice(0, 20), 256, 64);

    const texture = new THREE.CanvasTexture(canvas);
    const sign = new THREE.Mesh(
        new THREE.PlaneGeometry(3.2, 0.8),
        new THREE.MeshBasicMaterial({ map: texture })
    );

    sign.position.set(x, y, z);
    scene.add(sign);
}

// Back wall and store entrance
makeBox(28, 4, 0.4, "#c6d3dc", 0, 2, -11.8);
makeBox(0.4, 4, 24, "#c6d3dc", -13.8, 2, 0);
makeBox(0.4, 4, 24, "#c6d3dc", 13.8, 2, 0);
makeText("FAST MART", 0, 3.2, -11.55);

// Product placement and selection
const clickableProducts = [];
const raycaster = new THREE.Raycaster();
const pointer = new THREE.Vector2();

let products = [];
let selectedProduct = null;

// Each aisle has a double-sided shelf.
const aisleZ = [-6, -1, 4];

for (let aisle = 0; aisle < aisleZ.length; aisle++) {
    const z = aisleZ[aisle];

    makeBox(0.35, 2.1, 3.5, "#526477", -3.2, 1.05, z);
    makeBox(0.35, 2.1, 3.5, "#526477", 3.2, 1.05, z);

    for (const x of [-3.2, 3.2]) {
        for (const y of [0.5, 1.25, 2]) {
            makeBox(0.55, 0.12, 3.5, "#a8b8c6", x, y, z);
        }
    }

    makeText(
        ["FRUITS", "DAIRY", "GROCERIES"][aisle],
        0,
        3.2,
        z
    );
}

function addProductMeshes() {
    const palette = [
        "#e94f64", "#f5a623", "#65bd75",
        "#4a90e2", "#c47adf", "#e8d66d"
    ];

    products.forEach((product, index) => {
        // Spread product displays over the shelf positions.
        const aisle = Math.floor(index / 6) % aisleZ.length;
        const positionInAisle = index % 6;

        const side = positionInAisle < 3 ? -3.2 : 3.2;
        const shelfRow = Math.floor(positionInAisle / 3);
        const zOffset = (positionInAisle % 3 - 1) * 0.9;
        const y = shelfRow === 0 ? 0.85 : 1.65;
        const z = aisleZ[aisle] + zOffset;

        const color = palette[index % palette.length];

        const box = new THREE.Mesh(
            new THREE.BoxGeometry(0.55, 0.65, 0.55),
            new THREE.MeshStandardMaterial({
                color,
                roughness: 0.55
            })
        );

        box.position.set(side, y, z);
        box.castShadow = true;
        box.userData.product = product;
        box.userData.baseY = y;

        scene.add(box);
        clickableProducts.push(box);

        // Simple label board beneath each display item.
        const label = makeBox(
            0.62, 0.12, 0.58,
            "#f8fafc",
            side, y - 0.39, z
        );

        label.userData.product = product;
        clickableProducts.push(label);
    });
}

async function loadProducts() {
    message.textContent = "Loading products...";

    try {
        const response = await fetch("/api/products");

        if (!response.ok) {
            throw new Error("Product API returned an error.");
        }

        products = await response.json();
        addProductMeshes();

        message.textContent = products.length
            ? "Select any product on the shelves."
            : "No products found in MySQL.";
    } catch (error) {
        console.error(error);
        message.textContent =
            "Could not load products. Check Flask and MySQL.";
    }
}

function showSelectedProduct(product) {
    selectedProduct = product;
    addButton.disabled = !product || product.stock_quantity < 1;

    if (!product) {
        selectedPanel.textContent = "Click a product on the shelf.";
        return;
    }

    selectedPanel.replaceChildren();

    const name = document.createElement("h3");
    name.textContent = product.name;

    const category = document.createElement("p");
    category.textContent = product.category || "General";

    const price = document.createElement("p");
    price.className = "price";
    price.textContent = `₹${Number(product.price).toFixed(2)}`;

    const stock = document.createElement("p");
    stock.textContent = `Available stock: ${product.stock_quantity}`;

    selectedPanel.append(name, category, price, stock);
}

renderer.domElement.addEventListener("pointerdown", event => {
    const rect = renderer.domElement.getBoundingClientRect();

    pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

    raycaster.setFromCamera(pointer, camera);

    const hits = raycaster.intersectObjects(clickableProducts);

    if (hits.length) {
        const product = hits[0].object.userData.product;

        if (product) {
            showSelectedProduct(product);
            message.textContent = `Selected ${product.name}`;
        }
    }
});

// Add selected product using the existing Flask cart endpoint.
addButton.addEventListener("click", async () => {
    if (!selectedProduct) return;

    addButton.disabled = true;
    message.textContent = "Adding product...";

    try {
        const response = await fetch(
            `/cart/add/${selectedProduct.id}`,
            {
                method: "POST",
                credentials: "same-origin"
            }
        );

        if (!response.ok) {
            throw new Error("Could not add product.");
        }

        message.textContent = `${selectedProduct.name} added to cart.`;
    } catch (error) {
        console.error(error);
        message.textContent =
            "Could not add product. Please try again.";
    } finally {
        addButton.disabled = selectedProduct.stock_quantity < 1;
    }
});

// Basic mouse-drag camera rotation and zoom.
let dragging = false;
let previousX = 0;
let previousY = 0;
let rotation = 0;
let tilt = 0;

renderer.domElement.addEventListener("pointerdown", event => {
    dragging = true;
    previousX = event.clientX;
    previousY = event.clientY;
});

window.addEventListener("pointerup", () => {
    dragging = false;
});

window.addEventListener("pointermove", event => {
    if (!dragging) return;

    rotation += (event.clientX - previousX) * 0.006;
    tilt += (event.clientY - previousY) * 0.003;

    tilt = Math.max(-0.5, Math.min(0.7, tilt));

    previousX = event.clientX;
    previousY = event.clientY;

    updateCamera();
});

renderer.domElement.addEventListener("wheel", event => {
    event.preventDefault();

    const direction = camera.position.clone().normalize();
    camera.position.addScaledVector(
        direction,
        event.deltaY * 0.012
    );

    const distance = camera.position.length();

    if (distance < 8) camera.position.setLength(8);
    if (distance > 30) camera.position.setLength(30);
}, { passive: false });

function updateCamera() {
    const distance = 18;
    camera.position.set(
        Math.sin(rotation) * distance,
        9 + tilt * 8,
        Math.cos(rotation) * distance
    );
    camera.lookAt(0, 0, 0);
}

function animate() {
    requestAnimationFrame(animate);
    renderer.render(scene, camera);
}

window.addEventListener("resize", () => {
    const width = container.clientWidth;
    const height = container.clientHeight;

    camera.aspect = width / height;
    camera.updateProjectionMatrix();
    renderer.setSize(width, height);
});

loadProducts();
animate();

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import os

# -- Database Setup
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./inventory.db")

if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# -- ORM Model
class ProductModel(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    sku = Column(String, unique=True, nullable=False, index=True)
    category = Column(String, nullable=False)
    price = Column(Float, nullable=False)
    quantity = Column(Integer, default=0)
    description = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

Base.metadata.create_all(bind=engine)

# -- Pydantic Schemas
class ProductCreate(BaseModel):
    name: str
    sku: str
    category: str
    price: float
    quantity: int = 0
    description: Optional[str] = None

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    price: Optional[float] = None
    quantity: Optional[int] = None
    description: Optional[str] = None

class ProductOut(BaseModel):
    id: int
    name: str
    sku: str
    category: str
    price: float
    quantity: int
    description: Optional[str]
    created_at: datetime
    updated_at: datetime
    class Config:
        from_attributes = True

# -- App
app = FastAPI(title="Inventory API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:4200"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/", tags=["Health"])
def health():
    return {"status": "ok", "message": "Inventory API is running"}

@app.get("/products", response_model=List[ProductOut], tags=["Products"])
def list_products(skip: int = 0, limit: int = 100, category: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(ProductModel)
    if category:
        query = query.filter(ProductModel.category == category)
    return query.offset(skip).limit(limit).all()

@app.post("/products", response_model=ProductOut, status_code=201, tags=["Products"])
def create_product(product: ProductCreate, db: Session = Depends(get_db)):
    existing = db.query(ProductModel).filter(ProductModel.sku == product.sku).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"SKU '{product.sku}' already exists")
    db_product = ProductModel(**product.dict())
    db.add(db_product)
    db.commit()
    db.refresh(db_product)
    return db_product

@app.get("/products/{product_id}", response_model=ProductOut, tags=["Products"])
def get_product(product_id: int, db: Session = Depends(get_db)):
    product = db.query(ProductModel).filter(ProductModel.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product

@app.put("/products/{product_id}", response_model=ProductOut, tags=["Products"])
def update_product(product_id: int, updates: ProductUpdate, db: Session = Depends(get_db)):
    product = db.query(ProductModel).filter(ProductModel.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    for field, value in updates.dict(exclude_unset=True).items():
        setattr(product, field, value)
    product.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(product)
    return product

@app.delete("/products/{product_id}", tags=["Products"])
def delete_product(product_id: int, db: Session = Depends(get_db)):
    product = db.query(ProductModel).filter(ProductModel.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    db.delete(product)
    db.commit()
    return {"message": f"Product {product_id} deleted successfully"}

@app.get("/stats", tags=["Stats"])
def get_stats(db: Session = Depends(get_db)):
    products = db.query(ProductModel).all()
    total_products = len(products)
    total_value = sum(p.price * p.quantity for p in products)
    low_stock = sum(1 for p in products if p.quantity < 10)
    categories = list(set(p.category for p in products))
    return {"total_products": total_products, "total_value": round(total_value, 2), "low_stock_count": low_stock, "categories": categories}

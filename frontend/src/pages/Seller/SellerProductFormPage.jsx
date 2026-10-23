import { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import {
  getCategories,
  getSellerProduct,
  createSellerProduct,
  updateSellerProduct,
  ApiError,
} from '../../api/client';
import { PageLoader, ErrorMessage, Spinner, FieldErrors } from '../../components/UI';
import SellerLayout from './SellerLayout';

const BASE = import.meta.env.VITE_API_BASE_URL ?? '';

export default function SellerProductFormPage() {
  const { id } = useParams();
  const isEditing = Boolean(id);
  const navigate = useNavigate();

  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(isEditing);
  const [submitting, setSubmitting] = useState(false);

  const [form, setForm] = useState({
    title: '',
    price: '',
    category: '',
    quantity: '1',
    unit: 'box',
    min_order_quantity: '1',
    description: '',
  });

  const [existingImg, setExistingImg] = useState(null);
  const [imageFile, setImageFile] = useState(null);
  const [error, setError] = useState(null);
  const [details, setDetails] = useState(null);

  useEffect(() => {
    let isMounted = true;
    async function init() {
      try {
        const catRes = await getCategories();
        if (isMounted) {
          const validCats = (catRes.categories ?? []).filter(c => c.code !== 'ALL');
          setCategories(validCats);
          if (!isEditing && validCats.length > 0) {
            setForm(f => ({ ...f, category: validCats[0].code }));
          }
        }

        if (isEditing) {
          const prodRes = await getSellerProduct(id);
          if (isMounted && prodRes?.product) {
            const p = prodRes.product;
            setForm({
              title: p.title ?? '',
              price: String(p.price ?? ''),
              category: p.category ?? '',
              quantity: String(p.quantity ?? '1'),
              unit: p.unit ?? 'box',
              min_order_quantity: String(p.min_order_quantity ?? '1'),
              description: p.description ?? '',
            });
            if (p.image) {
              setExistingImg(`${BASE}${p.image.startsWith('/') ? '' : '/'}${p.image}`);
            }
          }
        }
      } catch (err) {
        if (isMounted) setError(err.message ?? 'Failed to load form data.');
      } finally {
        if (isMounted) setLoading(false);
      }
    }
    init();
    return () => { isMounted = false; };
  }, [id, isEditing]);

  function handleChange(e) {
    setForm(f => ({ ...f, [e.target.name]: e.target.value }));
  }

  function handleFileChange(e) {
    if (e.target.files && e.target.files[0]) {
      setImageFile(e.target.files[0]);
    }
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    setDetails(null);

    const formData = new FormData();
    formData.append('title', form.title);
    formData.append('price', form.price);
    formData.append('category', form.category);
    formData.append('quantity', form.quantity);
    formData.append('unit', form.unit);
    formData.append('min_order_quantity', form.min_order_quantity);
    formData.append('description', form.description);

    if (imageFile) {
      formData.append('image', imageFile);
    }

    try {
      if (isEditing) {
        await updateSellerProduct(id, formData);
      } else {
        await createSellerProduct(formData);
      }
      navigate('/seller/products', { replace: true });
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
        setDetails(err.details);
      } else {
        setError('Failed to save product.');
      }
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) return <SellerLayout><PageLoader /></SellerLayout>;

  return (
    <SellerLayout>
      <div className="seller-form-card">
        <h2 className="seller-form-card__title">
          {isEditing ? 'Edit Product' : 'Add New Bakery Product'}
        </h2>

        {error && <ErrorMessage message={error} />}

        <form onSubmit={handleSubmit} className="profile-form">
          {/* Title */}
          <div className="form-group">
            <label className="form-label" htmlFor="prod-title">Product Title</label>
            <input
              id="prod-title"
              name="title"
              type="text"
              className="form-input"
              value={form.title}
              onChange={handleChange}
              placeholder="e.g. Artisanal Sourdough Loaf"
              required
              disabled={submitting}
            />
            {details?.title && <FieldErrors errors={details.title} />}
          </div>

          {/* Category */}
          <div className="form-group">
            <label className="form-label" htmlFor="prod-category">Category</label>
            <select
              id="prod-category"
              name="category"
              className="form-input"
              value={form.category}
              onChange={handleChange}
              required
              disabled={submitting}
            >
              {categories.map(c => (
                <option key={c.code} value={c.code}>{c.label}</option>
              ))}
            </select>
            {details?.category && <FieldErrors errors={details.category} />}
          </div>

          {/* Price & Quantity Row */}
          <div className="form-row">
            <div className="form-group flex-1">
              <label className="form-label" htmlFor="prod-price">Price (€)</label>
              <input
                id="prod-price"
                name="price"
                type="number"
                step="0.01"
                min="0.01"
                className="form-input"
                value={form.price}
                onChange={handleChange}
                placeholder="4.50"
                required
                disabled={submitting}
              />
              {details?.price && <FieldErrors errors={details.price} />}
            </div>

            <div className="form-group flex-1">
              <label className="form-label" htmlFor="prod-qty">Stock Quantity</label>
              <input
                id="prod-qty"
                name="quantity"
                type="number"
                min="0"
                className="form-input"
                value={form.quantity}
                onChange={handleChange}
                placeholder="10"
                required
                disabled={submitting}
              />
              {details?.quantity && <FieldErrors errors={details.quantity} />}
            </div>
          </div>

          {/* Wholesale Packaging & MOQ Row */}
          <div className="form-row">
            <div className="form-group flex-1">
              <label className="form-label" htmlFor="prod-unit">Wholesale Packaging Unit</label>
              <input
                id="prod-unit"
                name="unit"
                type="text"
                className="form-input"
                value={form.unit}
                onChange={handleChange}
                placeholder="e.g. crate of 24, tray of 12, box, kg"
                required
                disabled={submitting}
              />
              {details?.unit && <FieldErrors errors={details.unit} />}
            </div>

            <div className="form-group flex-1">
              <label className="form-label" htmlFor="prod-moq">Minimum Order Quantity (MOQ)</label>
              <input
                id="prod-moq"
                name="min_order_quantity"
                type="number"
                min="1"
                className="form-input"
                value={form.min_order_quantity}
                onChange={handleChange}
                placeholder="1"
                required
                disabled={submitting}
              />
              {details?.min_order_quantity && <FieldErrors errors={details.min_order_quantity} />}
            </div>
          </div>

          {/* Description */}
          <div className="form-group">
            <label className="form-label" htmlFor="prod-desc">Description</label>
            <textarea
              id="prod-desc"
              name="description"
              rows={4}
              className="form-input"
              value={form.description}
              onChange={handleChange}
              placeholder="Describe the flavors, ingredients, and texture of this bake…"
              disabled={submitting}
            />
            {details?.description && <FieldErrors errors={details.description} />}
          </div>

          {/* Image */}
          <div className="form-group">
            <label className="form-label" htmlFor="prod-image">Product Image</label>
            {existingImg && (
              <div style={{ marginBottom: 'var(--sp-2)' }}>
                <span style={{ fontSize: 'var(--text-xs)', color: 'var(--clr-text-muted)' }}>Current Image:</span>
                <div className="image-preview-box">
                  <img src={existingImg} alt="Current product" />
                </div>
              </div>
            )}
            <input
              id="prod-image"
              name="image"
              type="file"
              accept="image/*"
              className="form-input"
              onChange={handleFileChange}
              disabled={submitting}
            />
            {details?.image && <FieldErrors errors={details.image} />}
          </div>

          {/* Actions */}
          <div style={{ display: 'flex', gap: 'var(--sp-3)', marginTop: 'var(--sp-4)' }}>
            <button
              type="submit"
              className="btn btn-primary btn-lg"
              disabled={submitting}
            >
              {submitting ? (
                <><Spinner size={16} /> Saving…</>
              ) : isEditing ? (
                'Save Changes'
              ) : (
                'Publish Product'
              )}
            </button>
            <Link to="/seller/products" className="btn btn-secondary btn-lg">
              Cancel
            </Link>
          </div>
        </form>
      </div>
    </SellerLayout>
  );
}
